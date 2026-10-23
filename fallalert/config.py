"""
Central configuration for the FallAlert backend.

Every port, URL, threshold and window lives here so the Docker image can be
re-pointed with environment variables alone - no code edits, no rebuild.

Port map
--------
    8000  outdoor detector  (internal; receives the phone sensor stream)
    8001  indoor detector   (edge machine only; never exposed)
    8002  Alert Manager     (the ONLY public endpoint the app talks to)
"""

import os


def _env_int(name, default):

    try:

        return int(os.environ.get(name, default))

    except (TypeError, ValueError):

        return int(default)


def _env_float(name, default):

    try:

        return float(os.environ.get(name, default))

    except (TypeError, ValueError):

        return float(default)


# ---------------------------------------------------------
# Event sources (requirement: every event is tagged indoor/outdoor)
# ---------------------------------------------------------

SOURCE_INDOOR = "indoor"

SOURCE_OUTDOOR = "outdoor"

VALID_SOURCES = (SOURCE_INDOOR, SOURCE_OUTDOOR)


# ---------------------------------------------------------
# Centralized Alert Manager
# ---------------------------------------------------------

ALERT_MANAGER_HOST = os.environ.get(
    "ALERT_MANAGER_HOST",
    "0.0.0.0"
)

ALERT_MANAGER_PORT = _env_int(
    "ALERT_MANAGER_PORT",
    8002
)

# Base address of the Manager. Both detectors POST their confirmed falls to
# ``ALERT_MANAGER_EVENT_URL``; the Android app polls ``/status``.
# In the container this stays on localhost; from the edge machine it is the
# public HTTPS address of the deployed service.
ALERT_MANAGER_BASE_URL = os.environ.get(
    "ALERT_MANAGER_URL",
    f"http://127.0.0.1:{ALERT_MANAGER_PORT}"
).rstrip("/")

ALERT_MANAGER_EVENT_URL = ALERT_MANAGER_BASE_URL + "/event"

ALERT_MANAGER_STATUS_URL = ALERT_MANAGER_BASE_URL + "/status"

# How long a confirmed event keeps the app-facing /status reporting fall=True.
# Comfortably covers the app's 20 second false-alarm cancel window.
ALERT_HOLD_SECONDS = _env_float(
    "ALERT_HOLD_SECONDS",
    30
)

# A second event from the same source inside this window is assumed to be the
# same physical fall and suppressed even if it carries a fresh event id.
SOURCE_COOLDOWN_SECONDS = _env_float(
    "SOURCE_COOLDOWN_SECONDS",
    15
)

# Memory of already-alerted event ids (idempotency).
EVENT_HISTORY_LIMIT = _env_int(
    "EVENT_HISTORY_LIMIT",
    200
)

# How long the sensor relay to the outdoor detector may take.
RELAY_TIMEOUT_SECONDS = _env_float(
    "RELAY_TIMEOUT_SECONDS",
    6.0
)


# ---------------------------------------------------------
# Shared secret (optional hardening)
# ---------------------------------------------------------
#
# When this is set, POST /event only accepts callers that also send the same
# value in the X-Alert-Token header. That stops anyone who merely learns the
# URL from firing a fake emergency alert.
#
# Left empty it is disabled, so local development needs no extra setup.
# The phone sensor relay (POST /) is intentionally NOT gated: the Sensor
# Logger client cannot add custom headers, and that path only forwards
# samples - it cannot raise an alert by itself.

ALERT_SHARED_TOKEN = os.environ.get(
    "ALERT_SHARED_TOKEN",
    ""
).strip()

ALERT_TOKEN_HEADER = "X-Alert-Token"


# ---------------------------------------------------------
# Outdoor detector (phone IMU -> LSTM)
# ---------------------------------------------------------

OUTDOOR_DETECTOR_HOST = os.environ.get(
    "OUTDOOR_DETECTOR_HOST",
    "0.0.0.0"
)

OUTDOOR_DETECTOR_PORT = _env_int(
    "OUTDOOR_DETECTOR_PORT",
    8000
)

# Where the Alert Manager relays the phone's sensor stream.
OUTDOOR_DETECTOR_URL = os.environ.get(
    "OUTDOOR_DETECTOR_URL",
    f"http://127.0.0.1:{OUTDOOR_DETECTOR_PORT}"
).rstrip("/")

OUTDOOR_THRESHOLD = _env_float(
    "OUTDOOR_THRESHOLD",
    0.40
)

# Rolling sample window the LSTM needs before it can predict.
OUTDOOR_WINDOW_SAMPLES = _env_int(
    "OUTDOOR_WINDOW_SAMPLES",
    200
)

# One report per physical fall episode from the outdoor detector.
REPORT_COOLDOWN_SECONDS = _env_float(
    "REPORT_COOLDOWN_SECONDS",
    15.0
)


# ---------------------------------------------------------
# Indoor detector (edge machine, webcam)
# ---------------------------------------------------------

INDOOR_DETECTOR_HOST = os.environ.get(
    "INDOOR_DETECTOR_HOST",
    "0.0.0.0"
)

# FALLALERT_PORT is kept as the variable name for continuity with the
# existing local setup and the Android app's documentation.
INDOOR_DETECTOR_PORT = _env_int(
    "FALLALERT_PORT",
    8001
)

INDOOR_FALL_THRESHOLD = _env_float(
    "INDOOR_FALL_THRESHOLD",
    0.50
)


# ---------------------------------------------------------
# Startup banner helper
# ---------------------------------------------------------

def describe_ports():

    return {
        "outdoor_detector": OUTDOOR_DETECTOR_PORT,
        "indoor_detector": INDOOR_DETECTOR_PORT,
        "alert_manager": ALERT_MANAGER_PORT
    }
