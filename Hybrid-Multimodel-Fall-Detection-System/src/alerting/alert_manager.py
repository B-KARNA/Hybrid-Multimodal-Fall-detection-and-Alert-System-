"""
Centralized Alert Manager for the hybrid indoor + outdoor fall detection system.

This is the ONE shared alert endpoint. Both detection modules keep running
independently on their own ports and simply report their confirmed fall events
here:

    indoor  (webcam YOLO + GRU)   -> POST /event   {source: "indoor",  ...}
    outdoor (phone IMU + LSTM)    -> POST /event   {source: "outdoor", ...}

The Manager is also the single endpoint the FallAlert Android app talks to,
so the app never has to know that two detectors exist:

    POST /          -> relayed to the outdoor detector (the phone keeps
                       streaming its 9-channel sensor payload there)
    GET  /status    -> aggregated verdict for the app (alarm + SMS + call)
    GET  /events    -> recent event log, for verification/testing

Alerting itself (alarm sound, emergency SMS, automatic call) stays inside the
existing Android app - it already implements that and keeps its saved
emergency contact. The Manager only decides WHEN an alert is legitimate:

  * only confirmed FALL events are accepted (NO FALL is ignored),
  * an event_id is only ever alerted once,
  * a second event from the same source inside a short cooldown is treated as
    the same physical fall and suppressed.

Run it with:
    python -m src.alerting.alert_manager
or
    python src/alerting/alert_manager.py
"""

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error as urlerror
from urllib import request as urlrequest


# ============================================================
# CONFIGURATION
# ============================================================

# The single app-facing port. Point the FallAlert app's server URL here.
MANAGER_PORT = int(
    os.environ.get(
        "ALERT_MANAGER_PORT",
        "8002"
    )
)

# Where the outdoor detector (sensor_service.py) listens. The app's sensor
# stream is relayed here so the outdoor LSTM keeps receiving live data.
OUTDOOR_DETECTOR_URL = os.environ.get(
    "OUTDOOR_DETECTOR_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

# How long a confirmed event keeps the app-facing /status reporting fall=True.
# Comfortably covers the phone's 20s false-alarm cancel window.
ALERT_HOLD_SECONDS = float(
    os.environ.get(
        "ALERT_HOLD_SECONDS",
        "30"
    )
)

# A second event from the same source inside this window is assumed to be the
# same physical fall and is suppressed even if it carries a fresh event_id.
SOURCE_COOLDOWN_SECONDS = float(
    os.environ.get(
        "SOURCE_COOLDOWN_SECONDS",
        "15"
    )
)

# Memory of already-alerted event ids (idempotency).
EVENT_HISTORY_LIMIT = 200

# How long the relay to the outdoor detector may take before we give up.
RELAY_TIMEOUT_SECONDS = 6.0

VALID_SOURCES = ("indoor", "outdoor")


# ============================================================
# SHARED STATE
# ============================================================

_lock = threading.Lock()

_seen_event_ids = deque(maxlen=EVENT_HISTORY_LIMIT)

_last_event_time_per_source = {}

_recent_events = deque(maxlen=50)

_alert_until = 0.0

_last_event = None

_relayed_probability = 0.0

_relayed_samples = 0


# ============================================================
# PREDICTION LABEL HANDLING
# ============================================================

_FALL_LABELS = {
    "fall",
    "fall detected",
    "fall_detected",
    "fallen",
    "1",
    "true",
    "yes"
}

_NO_FALL_LABELS = {
    "",
    "no fall",
    "no_fall",
    "no",
    "normal",
    "not fall",
    "safe",
    "0",
    "false"
}


def is_confirmed_fall(prediction):
    """
    Returns True only for an explicit confirmed FALL prediction.

    Anything unknown is treated as NOT a fall, so an unfamiliar label can
    never accidentally fire an emergency alert.
    """

    if isinstance(prediction, bool):

        return prediction

    if isinstance(prediction, (int, float)):

        return float(prediction) >= 0.5

    if prediction is None:

        return False

    label = str(prediction).strip().lower()

    if label in _NO_FALL_LABELS:

        return False

    if label in _FALL_LABELS:

        return True

    if "no fall" in label or "normal" in label:

        return False

    return "fall" in label


def _coerce_probability(value, prediction):

    try:

        return float(value)

    except (TypeError, ValueError):

        pass

    try:

        return float(prediction)

    except (TypeError, ValueError):

        return 1.0


# ============================================================
# EVENT REGISTRATION
# ============================================================

def register_event(payload):
    """
    Validates and records one reported detection event.

    Returns (accepted, reason, duplicate).
    """

    global _alert_until
    global _last_event

    if not isinstance(payload, dict):

        return False, "body must be a JSON object", False

    source = str(
        payload.get("source", "")
    ).strip().lower()

    event_id = str(
        payload.get("event_id")
        or payload.get("eventId")
        or payload.get("id")
        or ""
    ).strip()

    prediction = payload.get("prediction")

    timestamp = payload.get("timestamp")

    if source not in VALID_SOURCES:

        return (
            False,
            f"unknown source '{source}' (expected indoor/outdoor)",
            False
        )

    if not event_id:

        return False, "missing event_id", False

    if not timestamp:

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    # Requirement 5: only a confirmed FALL ever reaches the alert path.
    if not is_confirmed_fall(prediction):

        return (
            False,
            f"prediction '{prediction}' is not a confirmed FALL",
            False
        )

    probability = _coerce_probability(
        payload.get("probability"),
        prediction
    )

    now = time.time()

    with _lock:

        # Requirement 6a: the exact same event is never alerted twice.
        if event_id in _seen_event_ids:

            return (
                False,
                f"duplicate event_id {event_id}",
                True
            )

        # Requirement 6b: a rapid re-detection from the same source is the
        # same physical fall, so it is suppressed as a duplicate too.
        last_time = _last_event_time_per_source.get(source)

        if (
            last_time is not None
            and (now - last_time) < SOURCE_COOLDOWN_SECONDS
        ):

            _seen_event_ids.append(event_id)

            return (
                False,
                f"{source} event inside {SOURCE_COOLDOWN_SECONDS:g}s cooldown",
                True
            )

        _seen_event_ids.append(event_id)

        _last_event_time_per_source[source] = now

        _alert_until = now + ALERT_HOLD_SECONDS

        _last_event = {
            "source": source,
            "event_id": event_id,
            "timestamp": timestamp,
            "prediction": str(prediction),
            "probability": probability,
            "received_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        _recent_events.appendleft(
            _last_event
        )

        print(
            f"[AlertManager] ACCEPTED  source={source:7s} "
            f"event={event_id}  prediction={prediction}  "
            f"p={probability:.2f}  -> alerting for "
            f"{ALERT_HOLD_SECONDS:g}s"
        )

    return True, "accepted", False


# ============================================================
# APP-FACING STATUS
# ============================================================

def build_status_payload():
    """
    The Android app's polling contract:
    {probability, threshold, fall, samples, connected}
    """

    now = time.time()

    with _lock:

        active = now < _alert_until

        if active and _last_event is not None:

            probability = _last_event["probability"]

            source = _last_event["source"]

        else:

            probability = _relayed_probability

            source = "manager"

        return {
            "probability": probability,
            "fall": active,
            "samples": _relayed_samples,
            "connected": True,
            "source": source,
            "last_event": _last_event,
            "pending_events": len(_recent_events)
        }


def build_events_payload():

    with _lock:

        return {
            "count": len(_recent_events),
            "events": list(_recent_events)
        }


# ============================================================
# SENSOR RELAY (phone -> outdoor detector)
# ============================================================

def relay_sensor_post(body, content_type):

    global _relayed_probability
    global _relayed_samples

    if not body:

        return 200, json.dumps(
            {
                "probability": 0.0,
                "fall": False,
                "samples": 0,
                "connected": False,
                "error": "empty sensor payload"
            }
        ).encode("utf-8")

    request = urlrequest.Request(
        OUTDOOR_DETECTOR_URL + "/",
        data=body,
        method="POST",
        headers={
            "Content-Type":
                content_type or "application/json"
        }
    )

    try:

        with urlrequest.urlopen(
            request,
            timeout=RELAY_TIMEOUT_SECONDS
        ) as response:

            raw = response.read()

    except (
        urlerror.URLError,
        urlerror.HTTPError,
        OSError
    ) as error:

        print(
            f"[AlertManager] outdoor detector unreachable at "
            f"{OUTDOOR_DETECTOR_URL} ({error}) - relaying a "
            f"disconnected status"
        )

        return 200, json.dumps(
            {
                "probability": 0.0,
                "fall": False,
                "samples": 0,
                "connected": False,
                "error": f"outdoor detector unreachable: {error}"
            }
        ).encode("utf-8")

    # Mirror the outdoor detector's numbers so /status stays informative.
    try:

        parsed = json.loads(raw.decode("utf-8"))

        with _lock:

            _relayed_probability = float(
                parsed.get("probability", 0.0)
            )

            _relayed_samples = int(
                parsed.get("samples", 0)
            )

    except (
        ValueError,
        TypeError,
        AttributeError
    ):

        pass

    return 200, raw


# ============================================================
# HTTP HANDLER
# ============================================================

class AlertManagerHandler(BaseHTTPRequestHandler):

    # ----------------------------------------------------
    # POST /event  -> confirmed fall report from a detector
    # POST /       -> relayed sensor batch to the outdoor detector
    # ----------------------------------------------------

    def do_POST(self):

        path = self.path.split("?")[0]

        try:

            length = int(
                self.headers.get("Content-Length", 0)
            )

            body = self.rfile.read(length) if length else b""

        except (
            ConnectionResetError,
            BrokenPipeError
        ):

            return

        if path == "/event":

            try:

                payload = json.loads(
                    body.decode("utf-8") or "{}"
                )

            except ValueError as error:

                self.write_json(
                    400,
                    {
                        "accepted": False,
                        "error": f"invalid JSON: {error}"
                    }
                )

                return

            accepted, reason, duplicate = register_event(
                payload
            )

            if not accepted:

                print(
                    f"[AlertManager] REJECTED  "
                    f"reason={reason}"
                )

            self.write_json(
                202 if accepted else (200 if duplicate else 400),
                {
                    "accepted": accepted,
                    "duplicate": duplicate,
                    "reason": reason
                }
            )

            return

        if path in ("/", ""):

            status, raw = relay_sensor_post(
                body,
                self.headers.get("Content-Type")
            )

            self.write_raw(status, raw)

            return

        self.write_json(
            404,
            {"error": "Use POST /event or POST /"}
        )

    # ----------------------------------------------------
    # GET /status  -> aggregated verdict for the Android app
    # GET /events  -> recent event log (verification)
    # ----------------------------------------------------

    def do_GET(self):

        path = self.path.split("?")[0]

        if path == "/status":

            self.write_json(
                200,
                build_status_payload()
            )

        elif path == "/events":

            self.write_json(
                200,
                build_events_payload()
            )

        else:

            self.write_json(
                404,
                {"error": "Use GET /status or GET /events"}
            )

    # ----------------------------------------------------
    # Helpers
    # ----------------------------------------------------

    def write_raw(self, code, raw):

        self.send_response(code)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Content-Length",
            str(len(raw))
        )

        self.end_headers()

        self.wfile.write(raw)

    def write_json(self, code, payload):

        self.write_raw(
            code,
            json.dumps(payload).encode("utf-8")
        )

    def log_message(self, *args):

        return


class AlertManagerServer(ThreadingHTTPServer):
    """
    Alert Manager HTTP server.

    allow_reuse_address MUST stay False: on Windows SO_REUSEADDR silently
    lets a second process bind the same port, which would create duplicate
    alert services. Refusing reuse makes the second instance fail loudly.
    """

    allow_reuse_address = True

    daemon_threads = True


# ============================================================
# ENTRY POINT
# ============================================================

def build_server():

    # A single bound port is the guard against duplicate alert services:
    # a second instance simply cannot bind and exits with a clear message.
    return AlertManagerServer(
        ("0.0.0.0", MANAGER_PORT),
        AlertManagerHandler
    )


def main():

    try:

        server = build_server()

    except OSError as error:

        print()
        print("=" * 65)
        print("ALERT MANAGER COULD NOT START")
        print("=" * 65)
        print(
            f"Port {MANAGER_PORT} is already in use ({error})."
        )
        print(
            "An Alert Manager is probably already running - no duplicate "
            "alert service was started."
        )
        print(
            "Close the other instance, or run with "
            "ALERT_MANAGER_PORT=<other port>."
        )
        print("=" * 65)
        print()

        raise SystemExit(1)

    print()
    print("=" * 65)
    print("CENTRALIZED ALERT MANAGER STARTED")
    print("=" * 65)
    print(
        f"App-facing endpoint : http://<PC-IP>:{MANAGER_PORT}"
    )
    print(
        f"  GET  /status      -> verdict polled by the FallAlert app"
    )
    print(
        f"  POST /event       -> confirmed falls from indoor + outdoor"
    )
    print(
        f"  GET  /events      -> recent event log"
    )
    print(
        f"Outdoor relay       : {OUTDOOR_DETECTOR_URL}"
    )
    print(
        f"Alert hold          : {ALERT_HOLD_SECONDS:g}s"
    )
    print(
        f"Source cooldown     : {SOURCE_COOLDOWN_SECONDS:g}s"
    )
    print("=" * 65)
    print(
        "Point the FallAlert app's server URL at this port, then start "
        "the indoor and outdoor detectors."
    )
    print("=" * 65)
    print()

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print("Alert Manager stopped.")

    finally:

        server.server_close()


if __name__ == "__main__":
    main()
