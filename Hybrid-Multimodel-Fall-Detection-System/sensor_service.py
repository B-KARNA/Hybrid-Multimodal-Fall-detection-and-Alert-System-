from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import socket
import threading
from urllib import error as urlerror
from urllib import request as urlrequest
import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent

MODEL = ROOT / "models" / "outdoor" / "best_outdoor_lstm.keras"
SCALER = ROOT / "models" / "outdoor" / "outdoor_lstm_scaler.npz"

N = 200
THRESHOLD = 0.40

# ---------------------------------------------------------
# SHARED ALERT MANAGER
# ---------------------------------------------------------
# The outdoor detector keeps running independently on port 8000 and reports
# each confirmed fall to the one centralized Alert Manager, exactly like the
# indoor camera detector does.

ALERT_MANAGER_URL = os.environ.get(
    "ALERT_MANAGER_URL",
    "http://127.0.0.1:8002"
).rstrip("/") + "/event"

# No more than one outdoor event report per physical fall episode.
REPORT_COOLDOWN_SECONDS = 15.0

# ---------------------------------------------------------
# LOAD MODEL + SCALER
# ---------------------------------------------------------

model = tf.keras.models.load_model(MODEL)

s = np.load(SCALER)
mean = s["mean"]
std = s["std"]

safe_std = np.where(np.abs(std) < 1e-8, 1.0, std)

# Rolling sensor buffer
sensor_buffer = []
buffer_lock = threading.Lock()

latest_probability = 0.0


# ---------------------------------------------------------
# REPORT CONFIRMED FALLS TO THE SHARED ALERT MANAGER
# ---------------------------------------------------------

last_reported_at = 0.0
report_lock = threading.Lock()


def report_fall_event(probability):
    """
    Sends one confirmed outdoor fall to the centralized Alert Manager.

    The HTTP POST runs on a short-lived daemon thread so the phone's sensor
    request is answered immediately and the sensor stream is never blocked.
    """

    global last_reported_at

    now = time.time()

    with report_lock:

        if now - last_reported_at < REPORT_COOLDOWN_SECONDS:
            return

        last_reported_at = now

    event_id = uuid.uuid4().hex

    payload = json.dumps(
        {
            "source": "outdoor",
            "event_id": event_id,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "prediction": "FALL",
            "probability": float(probability)
        }
    ).encode("utf-8")

    def post():

        request = urlrequest.Request(
            ALERT_MANAGER_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json"
            }
        )

        try:

            with urlrequest.urlopen(
                request,
                timeout=5
            ) as response:

                print(
                    "[outdoor] Alert Manager accepted event "
                    f"{event_id}: "
                    f"{response.read().decode('utf-8')}"
                )

        except (
            urlerror.URLError,
            urlerror.HTTPError,
            OSError
        ) as error:

            print(
                "[outdoor] Could not reach Alert Manager at "
                f"{ALERT_MANAGER_URL} ({error}). "
                "Start it with: python -m src.alerting.alert_manager"
            )

    threading.Thread(
        target=post,
        daemon=True
    ).start()


# ---------------------------------------------------------
# EXTRACT 9 SENSOR VALUES FROM SENSOR LOGGER PAYLOAD
# ---------------------------------------------------------

def extract_sensor_values(payload):
    """
    Convert Sensor Logger payload into
    9-channel samples:

    acc_x, acc_y, acc_z,
    gravity_x, gravity_y, gravity_z,
    gyro_x, gyro_y, gyro_z
    """

    if not isinstance(payload, list):
        return []

    # Group sensor readings by timestamp
    grouped = {}

    for item in payload:

        if not isinstance(item, dict):
            continue

        name = item.get("name", "").lower()
        values = item.get("values", {})
        timestamp = item.get("time")

        if not isinstance(values, dict):
            continue

        if timestamp is None:
            continue

        try:
            x = float(values["x"])
            y = float(values["y"])
            z = float(values["z"])
        except (KeyError, TypeError, ValueError):
            continue

        if timestamp not in grouped:
            grouped[timestamp] = {}

        if name == "accelerometer":
            grouped[timestamp]["acc"] = [x, y, z]

        elif name == "gravity":
            grouped[timestamp]["gravity"] = [x, y, z]

        elif name == "gyroscope":
            grouped[timestamp]["gyro"] = [x, y, z]

    samples = []

    # 1. Try exact timestamp matching
    for timestamp in sorted(grouped):
        item = grouped[timestamp]
        if (
            "acc" in item
            and "gravity" in item
            and "gyro" in item
        ):
            samples.append(
                item["acc"]
                + item["gravity"]
                + item["gyro"]
            )

    if samples:
        return samples

    # 2. Fallback: pair readings by order if timestamps don't align exactly
    acc_list = []
    grav_list = []
    gyro_list = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        n = item.get("name", "").lower()
        v = item.get("values", {})
        if not isinstance(v, dict):
            continue
        try:
            vec = [float(v["x"]), float(v["y"]), float(v["z"])]
            if n == "accelerometer":
                acc_list.append(vec)
            elif n == "gravity":
                grav_list.append(vec)
            elif n == "gyroscope":
                gyro_list.append(vec)
        except (KeyError, TypeError, ValueError):
            continue

    min_count = min(len(acc_list), len(grav_list), len(gyro_list))
    for i in range(min_count):
        samples.append(acc_list[i] + grav_list[i] + gyro_list[i])

    return samples
# ---------------------------------------------------------
# LSTM PREDICTION
# ---------------------------------------------------------

def predict_from_buffer():

    global sensor_buffer

    if len(sensor_buffer) < N:
        return None

    data = np.asarray(
        sensor_buffer[-N:],
        dtype=np.float32
    )

    if data.shape != (N, 9):
        return None

    X = (data - mean) / safe_std
    X = X.reshape(1, N, 9)

    probability = model.predict(
        X,
        verbose=0
    ).ravel()[0]

    return float(probability)


# ---------------------------------------------------------
# HTTP SERVER
# ---------------------------------------------------------

class SensorHandler(BaseHTTPRequestHandler):

    def do_POST(self):

        global sensor_buffer
        global latest_probability

        try:

            length = int(
                self.headers.get("Content-Length", 0)
            )

            body = self.rfile.read(length)

            data = json.loads(
                body.decode("utf-8")
            )

            print(
                "PHONE POST:",
                data.keys() if isinstance(data, dict)
                else type(data)
            )

            # -------------------------------------------------
            # Sensor Logger sends data inside "payload"
            # -------------------------------------------------

            payload = data.get(
                "payload",
                data
            )
            print("PAYLOAD SAMPLE:", json.dumps(payload)[:3000])

            new_samples = extract_sensor_values(
                payload
            )

            if not new_samples:

                raise ValueError(
                    "Could not extract the 9 required "
                    "sensor values from Sensor Logger payload."
                )

            sensor_buffer.extend(
                new_samples
            )

            # Keep only latest samples
            if len(sensor_buffer) > N:
                sensor_buffer = sensor_buffer[-N:]

            # Need 200 samples before LSTM prediction
            probability = predict_from_buffer()

            # Physical kinematics check on recent sensor buffer (captures real drop and impact shocks)
            recent_data = np.asarray(sensor_buffer, dtype=np.float32)
            max_acc = 9.81
            min_acc = 9.81
            if len(recent_data) > 0:
                # Inspect the most recent 50 samples (last ~1.5 seconds of motion)
                window = recent_data[-50:]
                acc_mags = np.sqrt(np.sum(window[:, 0:3] ** 2, axis=1))
                max_acc = float(np.max(acc_mags))
                min_acc = float(np.min(acc_mags))

            # Fall detected if:
            # 1. Physical motion shows a drop (< 6.0 m/s^2) followed by collision impact (> 16.0 m/s^2) or severe shock (> 22.0 m/s^2)
            # 2. Or the LSTM neural network predicts probability >= threshold
            kinematic_fall = (max_acc >= 16.0 and min_acc <= 6.0) or (max_acc >= 22.0)
            lstm_fall = (probability is not None and probability >= THRESHOLD)

            fall = kinematic_fall or lstm_fall

            if kinematic_fall:
                latest_probability = max(probability if probability is not None else 0.0, 0.945)
            elif probability is not None:
                latest_probability = probability

            # Requirement: only a confirmed FALL is forwarded to the shared
            # Alert Manager - NO FALL predictions are never reported.
            if fall:
                report_fall_event(latest_probability)

            if probability is not None or kinematic_fall:
                print(
                    f"Samples: {len(sensor_buffer)}/{N} | "
                    f"Peak Acc: {max_acc:.2f} m/s² | "
                    f"Min Acc: {min_acc:.2f} m/s² | "
                    f"Probability: {latest_probability:.4f} | "
                    f"Fall: {fall}"
                )
            else:
                print(
                    f"Samples: {len(sensor_buffer)}/{N} | "
                    f"Peak Acc: {max_acc:.2f} m/s² | "
                    f"Collecting samples..."
                )

            response = {
                "probability": latest_probability,
                "threshold": THRESHOLD,
                "fall": fall,
                "samples": len(sensor_buffer),
                "connected": True
            }

            out = json.dumps(
                response
            ).encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json"
            )
            self.send_header(
                "Access-Control-Allow-Origin",
                "*"
            )
            self.end_headers()

            self.wfile.write(out)

        except Exception as e:

            print(
                "Sensor error:",
                str(e)
            )

            out = json.dumps({
                "error": str(e),
                "connected": True
            }).encode("utf-8")

            self.send_response(400)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()

            self.wfile.write(out)


    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    def do_GET(self):

        if self.path == "/status":

            response = {
                "probability": latest_probability,
                "threshold": THRESHOLD,
                "fall": (
                    latest_probability >= THRESHOLD
                ),
                "samples": len(sensor_buffer),
                "connected": True
            }

            out = json.dumps(
                response
            ).encode("utf-8")

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()

            self.wfile.write(out)

        else:

            self.send_response(404)
            self.end_headers()


    def log_message(self, *args):
        return


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

print("=" * 60)
print("LIVE PHONE SENSOR MONITOR")
print("=" * 60)
print(
    "Sensor Logger receiver: "
    "http://0.0.0.0:8000"
)
print(
    "Required sensors: "
    "Accelerometer + Gravity + Gyroscope"
)
print("Channels: 9")
print("Rolling window: 200 samples")
print("Fall threshold:", THRESHOLD)
print("Confirmed falls reported to:", ALERT_MANAGER_URL)
print("Waiting for Sensor Logger...")
print("=" * 60)

PORT = int(os.environ.get("SENSOR_PORT", "8000"))
server = HTTPServer(
    ("0.0.0.0", PORT),
    SensorHandler
)

server.serve_forever()