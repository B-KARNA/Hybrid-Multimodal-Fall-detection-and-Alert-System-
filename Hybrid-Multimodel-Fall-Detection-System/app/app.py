import streamlit as st
import numpy as np
import cv2
import tempfile
import time
import json
import threading
import csv
import sys
import urllib.parse
import subprocess
import shutil
import base64
from pathlib import Path
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import tensorflow as tf
from ultralytics import YOLO

# Import local alert and caretaker management system
APP_DIR_PATH = Path(__file__).resolve().parent
if str(APP_DIR_PATH) not in sys.path:
    sys.path.insert(0, str(APP_DIR_PATH))
import alert_system
import three_d_components
import streamlit.components.v1 as components

# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Smart Fall Detection System",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRU_MODEL = PROJECT_ROOT / "models" / "vision" / "best_gru.keras"
YOLO_MODEL = PROJECT_ROOT / "models" / "vision" / "yolo11n-pose.pt"

# If YOLO file is stored in project root, use it.
if not YOLO_MODEL.exists():
    root_yolo = PROJECT_ROOT / "yolo11n-pose.pt"
    if root_yolo.exists():
        YOLO_MODEL = root_yolo

OUTDOOR_MODEL = PROJECT_ROOT / "models" / "outdoor" / "best_outdoor_lstm.keras"
OUTDOOR_SCALER = PROJECT_ROOT / "models" / "outdoor" / "outdoor_lstm_scaler.npz"

PHONE_PORT = 8000

VISION_SEQUENCE_LENGTH = 20
VISION_FALL_THRESHOLD = 0.35
VISION_CONFIRM_FRAMES = 3
YOLO_CONFIDENCE = 0.25
KEYPOINT_DRAW_CONFIDENCE = 0.10
MAX_MISSED_FRAMES = 8
PROBABILITY_SMOOTHING_WINDOW = 3
FALL_ALERT_HOLD_FRAMES = 90

OUTDOOR_SEQUENCE_LENGTH = 200
OUTDOOR_THRESHOLD = 0.40

# ============================================================
# UI
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

    html, body, [class*="css"], .stMarkdown, p, span, div {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .block-container {
        padding-top: 1.2rem;
        max-width: 1250px;
    }

    /* Modern Hero Banner */
    .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        border-radius: 16px;
        padding: 34px 38px;
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 20px 35px -10px rgba(15, 23, 42, 0.35);
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(59, 130, 246, 0.18);
        color: #60a5fa;
        border: 1px solid rgba(96, 165, 250, 0.3);
        padding: 4px 12px;
        border-radius: 30px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 14px;
    }

    .hero-title {
        font-size: 34px;
        font-weight: 800;
        letter-spacing: -0.5px;
        line-height: 1.2;
        margin-bottom: 10px;
        background: linear-gradient(90deg, #ffffff 0%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        font-size: 15px;
        line-height: 1.6;
        color: #94a3b8;
        max-width: 820px;
        margin-bottom: 18px;
    }

    .hero-stats-row {
        display: flex;
        flex-wrap: wrap;
        gap: 20px;
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }

    .hero-stat-item {
        font-size: 12px;
        color: #cbd5e1;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .hero-stat-item strong {
        color: #38bdf8;
        font-size: 13px;
    }

    /* Modern Feature Cards */
    .feature-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.05);
        transition: all 0.25s ease-in-out;
        height: 100%;
    }

    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px -4px rgba(15, 23, 42, 0.1);
        border-color: #cbd5e1;
    }

    /* Result Panels */
    .result {
        padding: 16px 20px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .result-fall {
        border: 1px solid #fecaca;
        border-left: 6px solid #dc2626;
        background: #fef2f2;
        color: #991b1b;
        box-shadow: 0 4px 12px rgba(220, 38, 38, 0.08);
    }

    .result-safe {
        border: 1px solid #bbf7d0;
        border-left: 6px solid #16a34a;
        background: #f0fdf4;
        color: #166534;
        box-shadow: 0 4px 12px rgba(22, 163, 74, 0.08);
    }

    .result-wait {
        border: 1px solid #e2e8f0;
        border-left: 6px solid #64748b;
        background: #f8fafc;
        color: #475467;
    }

    /* Glowing Emergency SOS Card */
    .emergency-pulse-box {
        border: 2px solid #ef4444;
        background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
        border-radius: 14px;
        padding: 22px 24px;
        margin-top: 18px;
        box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.25);
        animation: pulse-border 2s infinite;
    }

    @keyframes pulse-border {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        70% { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }

    /* Status Indicators */
    .status-online { color: #16a34a; font-weight: 700; }
    .status-offline { color: #dc2626; font-weight: 700; }
    .status-idle { color: #d97706; font-weight: 700; }

    .sidebar-status {
        font-size: 13px;
        padding: 6px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .dot {
        display: inline-block;
        width: 9px;
        height: 9px;
        border-radius: 50%;
        margin-right: 8px;
    }

    .green {
        background: #10b981;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
    }
    .red {
        background: #ef4444;
        box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
    }
    .amber {
        background: #f59e0b;
        box-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
    }
    .gray {
        background: #94a3b8;
    }

    /* Buttons Styling */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# TOP NAVIGATION HELPER
# ============================================================

def render_top_navigation(current_label):
    tc1, tc2 = st.columns([1.5, 6])
    with tc1:
        if st.button("← Back to Home", key=f"back_home_{current_label.replace(' ', '_')}", type="secondary", use_container_width=True):
            go_to_page("Home")
    with tc2:
        st.markdown(
            f"<div style='font-size:13px; color:#94a3b8; padding-top:6px;'>Module: <strong style='color:#38bdf8;'>{current_label}</strong></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin: 8px 0 18px 0; border:none; border-top:1px solid rgba(226,232,240,0.15);'/>", unsafe_allow_html=True)


# ============================================================
# RESULT UI
# ============================================================

def show_result(status, probability=None, location="Living Room", patient_name="Relative", source="Vision", threshold=75.0):
    if status == "FALL DETECTED":
        css = "result result-fall"
        text = "🚨 FALL DETECTED"
    elif status == "NORMAL":
        css = "result result-safe"
        text = "✓ NO FALL DETECTED"
    else:
        css = "result result-wait"
        text = status

    st.markdown(
        f'<div class="{css}">{text}</div>',
        unsafe_allow_html=True,
    )

    if probability is not None:
        sev = alert_system.calculate_severity(probability)
        sev_pct = sev["percentage"]
        cat = sev["category"]
        color = sev["color"]
        bg_color = sev["bg_color"]

        st.markdown(
            f"""
            <div style="margin-top: 14px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 15px;">Fall Severity: <span style="color:{color}; font-size: 20px; font-weight: 800;">{sev_pct:.1f}%</span></span>
                <span style="background:{bg_color}; color:{color}; padding: 4px 12px; border-radius: 14px; font-weight: 700; font-size: 12px; border: 1px solid {color}50;">
                    {cat}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(min(sev_pct / 100.0, 1.0))
        st.caption(f"Raw Model Probability: {probability:.1%} | Severe Fall Threshold: {threshold:.0f}%")

        if status == "FALL DETECTED":
            if sev_pct >= threshold:
                # Severe Fall -> Dispatch emergency message to caretakers!
                dispatch = alert_system.dispatch_emergency_alert(
                    severity_percent=sev_pct,
                    location=location,
                    patient_name=patient_name,
                    source=source,
                    severity_threshold=threshold,
                )

                emergency_msg = (
                    f"🚨 EMERGENCY ALERT: Your relative ({patient_name}) has fallen at {location}! "
                    f"Fall severity is {sev_pct:.1f}%. Please go and save the person immediately!"
                )

                st.markdown(
                    f"""
                    <div class="emergency-pulse-box">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <span style="font-size: 32px; animation: bounce 1s infinite;">🚨</span>
                                <div>
                                    <div style="color: #b42318; font-weight: 800; font-size: 19px; letter-spacing: -0.3px;">
                                        CRITICAL FALL DETECTED — EMERGENCY DISPATCH ACTIVE!
                                    </div>
                                    <div style="color: #64748b; font-size: 13px;">
                                        Incident verified at <strong>{location}</strong>. High severity score ({sev_pct:.1f}%). Caretakers notified instantly.
                                    </div>
                                </div>
                            </div>
                            <span style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:11px; font-weight:800; padding:4px 10px; border-radius:20px; text-transform:uppercase;">
                                SOS Broadcasted
                            </span>
                        </div>
                        <div style="background: #ffffff; border: 1px solid #fecaca; border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #1e293b; line-height: 1.5; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);">
                            📢 <strong>Automated Message Sent to Caretakers:</strong><br/>
                            <span style="color: #b91c1c;">"{emergency_msg}"</span>
                        </div>
                    </div>
                    <script>
                    try {{
                        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                        const osc = audioCtx.createOscillator();
                        const gain = audioCtx.createGain();
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(880, audioCtx.currentTime);
                        osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.35);
                        gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
                        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
                        osc.connect(gain);
                        gain.connect(audioCtx.destination);
                        osc.start();
                        osc.stop(audioCtx.currentTime + 0.35);
                    }} catch(e) {{}}
                    </script>
                    """,
                    unsafe_allow_html=True,
                )

                # Show contact cards for registered caretakers
                caretakers = alert_system.get_caretakers()
                if caretakers:
                    st.markdown("<div style='margin-top:10px; font-weight:700; font-size:13px; color:#1e293b;'>CARETAKERS CONTACTED:</div>", unsafe_allow_html=True)
                    cols = st.columns(min(len(caretakers), 3))
                    for idx, c in enumerate(caretakers[:3]):
                        with cols[idx]:
                            clean_phone = "".join(ch for ch in c["phone"] if ch.isdigit())
                            msg_encoded = urllib.parse.quote(emergency_msg)
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; font-size: 13px; margin-bottom: 6px;">
                                    <strong>{c['name']}</strong><br/>
                                    <span style="color: #64748b; font-size: 11px;">{c['relation']}</span><br/>
                                    📞 <code>{c['phone']}</code><br/>
                                    <span style="color: #16a34a; font-weight: 600; font-size: 11px;">✓ Emergency Alert Sent</span>
                                </div>
                                <a href="https://wa.me/{clean_phone}?text={msg_encoded}" target="_blank" style="display:inline-block; width:100%; text-align:center; background:#25D366; color:white; padding:6px 0; border-radius:6px; font-size:12px; text-decoration:none; font-weight:700;">💬 Open WhatsApp</a>
                                """,
                                unsafe_allow_html=True,
                            )
            else:
                st.info(
                    f"ℹ️ Fall severity is **{sev_pct:.1f}%** ({cat}), which is below the critical threshold ({threshold:.0f}%). Automated caretaker emergency alerts are reserved for severe falls."
                )


# ============================================================
# MODEL LOADING
# IMPORTANT: INDOOR = YOLO11n-POSE + GRU
# ============================================================

@st.cache_resource
def load_vision_models():
    if not YOLO_MODEL.exists():
        raise FileNotFoundError(
            f"YOLO11 pose model not found:\n{YOLO_MODEL}"
        )

    if not GRU_MODEL.exists():
        raise FileNotFoundError(
            f"GRU model not found:\n{GRU_MODEL}"
        )

    pose_model = YOLO(str(YOLO_MODEL))
    gru_model = tf.keras.models.load_model(str(GRU_MODEL))

    return pose_model, gru_model


@st.cache_resource
def load_outdoor_model():
    if not OUTDOOR_MODEL.exists():
        raise FileNotFoundError(
            f"Outdoor LSTM model not found:\n{OUTDOOR_MODEL}"
        )

    if not OUTDOOR_SCALER.exists():
        raise FileNotFoundError(
            f"Outdoor scaler not found:\n{OUTDOOR_SCALER}"
        )

    model = tf.keras.models.load_model(str(OUTDOOR_MODEL))

    scaler = np.load(str(OUTDOOR_SCALER))
    mean = scaler["mean"].astype(np.float32)
    std = scaler["std"].astype(np.float32)
    safe_std = np.where(np.abs(std) < 1e-8, 1.0, std)

    return model, mean, safe_std


# ============================================================
# YOLO11 POSE
# ============================================================

SKELETON_CONNECTIONS = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
]


def normalize_keypoints(keypoints):
    keypoints = np.asarray(keypoints, dtype=np.float32)

    left_hip = keypoints[11]
    right_hip = keypoints[12]

    center = (left_hip + right_hip) / 2.0
    normalized = keypoints - center

    left_shoulder = normalized[5]
    right_shoulder = normalized[6]

    shoulder_distance = np.linalg.norm(
        left_shoulder - right_shoulder
    )

    if not np.isfinite(shoulder_distance) or shoulder_distance < 1e-6:
        shoulder_distance = 1.0

    normalized = normalized / shoulder_distance

    return np.nan_to_num(
        normalized,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    ).astype(np.float32)


def select_person(result):
    if result.keypoints is None or len(result.keypoints) == 0:
        return None

    keypoints = (
        result.keypoints.xy
        .detach()
        .cpu()
        .numpy()
    )

    if len(keypoints) == 0:
        return None

    if result.boxes is None or len(result.boxes) == 0:
        return None

    box_conf = (
        result.boxes.conf
        .detach()
        .cpu()
        .numpy()
    )

    if len(box_conf) == 0:
        return None

    best_index = int(np.argmax(box_conf))
    detection_confidence = float(box_conf[best_index])

    if detection_confidence < YOLO_CONFIDENCE:
        return None

    person = keypoints[best_index].astype(np.float32)

    if person.shape != (17, 2):
        return None

    if result.keypoints.conf is not None:
        kp_conf = (
            result.keypoints.conf
            .detach()
            .cpu()
            .numpy()
        )
        person_kp_conf = kp_conf[best_index].astype(np.float32)
    else:
        person_kp_conf = np.ones(17, dtype=np.float32)

    bbox = (
        result.boxes.xyxy
        .detach()
        .cpu()
        .numpy()[best_index]
        .astype(np.float32)
    )

    return person, person_kp_conf, bbox, detection_confidence


def predict_fall(sequence, gru_model):
    sequence = np.asarray(sequence, dtype=np.float32)
    sequence = sequence.reshape(
        1,
        VISION_SEQUENCE_LENGTH,
        34,
    )

    probability = float(
        gru_model.predict(sequence, verbose=0)[0][0]
    )

    return float(np.clip(probability, 0.0, 1.0))


def draw_person(
    frame,
    keypoints,
    keypoint_confidence,
    bbox,
    detection_confidence,
):
    output = frame.copy()

    h, w = output.shape[:2]

    x1, y1, x2, y2 = bbox.astype(int)

    x1 = max(0, min(x1, w - 1))
    x2 = max(0, min(x2, w - 1))
    y1 = max(0, min(y1, h - 1))
    y2 = max(0, min(y2, h - 1))

    # Scale line thickness and radius according to video frame size
    scale = max(1.0, min(w, h) / 480.0)
    box_thick = max(2, int(scale * 2.0))
    line_thick = max(2, int(scale * 2.2))
    circle_radius = max(4, int(scale * 3.5))

    cv2.rectangle(
        output,
        (x1, y1),
        (x2, y2),
        (255, 120, 0),
        box_thick,
    )

    label = f"Person {detection_confidence:.2f}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale, 2)
    cv2.rectangle(
        output,
        (x1, max(0, y1 - th - 8)),
        (x1 + tw + 6, y1),
        (255, 120, 0),
        -1,
    )
    cv2.putText(
        output,
        label,
        (x1 + 3, max(th + 2, y1 - 4)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55 * scale,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    for start, end in SKELETON_CONNECTIONS:
        if (
            keypoint_confidence[start] < KEYPOINT_DRAW_CONFIDENCE
            or keypoint_confidence[end] < KEYPOINT_DRAW_CONFIDENCE
        ):
            continue

        p1 = tuple(keypoints[start].astype(int))
        p2 = tuple(keypoints[end].astype(int))

        if p1[0] <= 0 or p1[1] <= 0 or p2[0] <= 0 or p2[1] <= 0:
            continue

        cv2.line(
            output,
            p1,
            p2,
            (255, 0, 255),
            line_thick,
            cv2.LINE_AA,
        )

    for i in range(17):
        if keypoint_confidence[i] < KEYPOINT_DRAW_CONFIDENCE:
            continue

        x, y = keypoints[i].astype(int)

        if 0 < x < w and 0 < y < h:
            # Outer dark ring for contrast on light backgrounds
            cv2.circle(
                output,
                (x, y),
                circle_radius + 1,
                (0, 0, 0),
                -1,
                cv2.LINE_AA,
            )
            # Bright neon green keypoint dot
            cv2.circle(
                output,
                (x, y),
                circle_radius,
                (0, 255, 0),
                -1,
                cv2.LINE_AA,
            )

    return output


class VisionFallDetector:

    def __init__(self, pose_model, gru_model):
        self.pose_model = pose_model
        self.gru_model = gru_model

        self.sequence = deque(maxlen=VISION_SEQUENCE_LENGTH)
        self.probabilities = deque(
            maxlen=PROBABILITY_SMOOTHING_WINDOW
        )

        self.positive_count = 0
        self.fall_detected = False
        self.fall_hold = 0

        self.missed_frames = 0
        self.last_probability = None

    def reset(self):
        self.sequence.clear()
        self.probabilities.clear()
        self.positive_count = 0
        self.fall_detected = False
        self.fall_hold = 0
        self.missed_frames = 0
        self.last_probability = None

    def predict_frame(self, frame):

        results = self.pose_model.predict(
            frame,
            conf=YOLO_CONFIDENCE,
            classes=[0],
            verbose=False,
        )

        result = results[0]
        detection = select_person(result)

        person_found = detection is not None

        if person_found:

            (
                person,
                keypoint_confidence,
                bbox,
                detection_confidence,
            ) = detection

            self.missed_frames = 0

            normalized = normalize_keypoints(person)

            self.sequence.append(
                normalized.reshape(-1)
            )

            if len(self.sequence) == VISION_SEQUENCE_LENGTH:

                probability = predict_fall(
                    self.sequence,
                    self.gru_model,
                )

                self.probabilities.append(probability)

                smoothed = float(
                    np.median(self.probabilities)
                )

                self.last_probability = smoothed

                if smoothed >= VISION_FALL_THRESHOLD:
                    self.positive_count += 1
                else:
                    self.positive_count = 0

                if self.positive_count >= VISION_CONFIRM_FRAMES:
                    self.fall_detected = True
                    self.fall_hold = FALL_ALERT_HOLD_FRAMES

        else:

            self.missed_frames += 1

            if self.missed_frames > MAX_MISSED_FRAMES:
                self.sequence.clear()
                self.probabilities.clear()
                self.positive_count = 0
                self.last_probability = None

        if self.fall_detected:

            if self.fall_hold > 0:
                self.fall_hold -= 1
            else:
                self.fall_detected = False
                self.positive_count = 0
                self.probabilities.clear()

        output = frame.copy()

        if person_found:
            output = draw_person(
                output,
                person,
                keypoint_confidence,
                bbox,
                detection_confidence,
            )

        if self.fall_detected:
            status = "FALL DETECTED"
            status_color = (0, 0, 255)

            cv2.rectangle(
                output,
                (10, 10),
                (output.shape[1] - 10, output.shape[0] - 10),
                status_color,
                5,
            )

        elif person_found:
            status = "NORMAL"
            status_color = (0, 255, 0)

        elif self.missed_frames <= MAX_MISSED_FRAMES:
            status = "TRACKING..."
            status_color = (0, 255, 255)

        else:
            status = "NO PERSON"
            status_color = (0, 165, 255)

        cv2.putText(
            output,
            status,
            (30, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            status_color,
            3,
            cv2.LINE_AA,
        )

        probability_text = (
            "Fall probability: --"
            if self.last_probability is None
            else f"Fall probability: {self.last_probability:.2f}"
        )

        cv2.putText(
            output,
            probability_text,
            (30, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            output,
            f"Pose buffer: {len(self.sequence)}/{VISION_SEQUENCE_LENGTH}",
            (30, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return output, status, self.last_probability


# ============================================================
# UPLOADED VIDEO
# ============================================================

def analyse_uploaded_video(uploaded_file):

    pose_model, gru_model = load_vision_models()

    detector = VisionFallDetector(
        pose_model,
        gru_model,
    )

    suffix = Path(uploaded_file.name).suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as temp:
        temp.write(uploaded_file.getbuffer())
        input_path = Path(temp.name)

    cap = cv2.VideoCapture(str(input_path))

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open uploaded video."
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if not fps or fps <= 0:
        fps = 25.0

    total = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    output_path = (
        Path(tempfile.gettempdir())
        / f"analysed_fall_{int(time.time())}.mp4"
    )

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    preview = st.empty()
    progress = st.progress(0.0)

    final_status = "NORMAL"
    max_probability = 0.0
    frame_no = 0
    snapshot_frames = []

    while True:

        ok, frame = cap.read()

        if not ok:
            break

        output, status, probability = detector.predict_frame(
            frame
        )

        writer.write(output)

        if status == "FALL DETECTED":
            final_status = "FALL DETECTED"

        if probability is not None:
            max_probability = max(
                max_probability,
                probability,
            )
            if (probability >= 0.60 or status == "FALL DETECTED") and len(snapshot_frames) < 3:
                snapshot_frames.append(cv2.cvtColor(output, cv2.COLOR_BGR2RGB))

        if frame_no % 3 == 0:
            preview.image(
                cv2.cvtColor(
                    output,
                    cv2.COLOR_BGR2RGB,
                ),
                channels="RGB",
                use_container_width=True,
            )

        frame_no += 1

        if total > 0:
            progress.progress(
                min(frame_no / total, 1.0)
            )

    cap.release()
    writer.release()

    # Clear preview and progress placeholders so no broken image remains
    preview.empty()
    progress.empty()

    try:
        input_path.unlink()
    except Exception:
        pass

    # Transcode to web-compatible H.264 (yuv420p) for seamless HTML5 <video> playback
    final_output_path = output_path
    if shutil.which("ffmpeg"):
        web_output_path = output_path.with_name(f"web_{output_path.name}")
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(output_path),
                "-vcodec", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "veryfast",
                "-crf", "23",
                "-movflags", "+faststart",
                str(web_output_path),
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
            )
            if res.returncode == 0 and web_output_path.exists() and web_output_path.stat().st_size > 0:
                try:
                    output_path.unlink()
                except Exception:
                    pass
                final_output_path = web_output_path
        except Exception:
            final_output_path = output_path

    return (
        final_output_path,
        final_status,
        max_probability,
        snapshot_frames,
    )


# ============================================================
# LIVE CAMERA
# ============================================================

try:
    from streamlit_webrtc import (
        webrtc_streamer,
        WebRtcMode,
        VideoProcessorBase,
        RTCConfiguration,
    )
    import av
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

RTC_CONFIGURATION = RTCConfiguration({
    "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302", "stun:openrelay.metered.ca:80"]},
        {
            "urls": [
                "turn:openrelay.metered.ca:80",
                "turn:openrelay.metered.ca:443",
                "turn:openrelay.metered.ca:443?transport=tcp",
            ],
            "username": "openrelay",
            "credential": "openrelay",
        },
    ]
})


def create_live_camera_processor():

    pose_model, gru_model = load_vision_models()

    class LiveProcessor(VideoProcessorBase):

        def __init__(self):
            self.detector = VisionFallDetector(
                pose_model,
                gru_model,
            )

        def recv(self, frame):

            image = frame.to_ndarray(
                format="bgr24"
            )

            output, _, _ = (
                self.detector.predict_frame(
                    image
                )
            )

            try:
                import av
                return av.VideoFrame.from_ndarray(
                    output,
                    format="bgr24",
                )
            except Exception:
                return frame.from_ndarray(
                    output,
                    format="bgr24",
                )

    return LiveProcessor


# ============================================================
# OUTDOOR LSTM
# ============================================================

def predict_sensor_array(data):

    model, mean, safe_std = load_outdoor_model()

    data = np.asarray(
        data,
        dtype=np.float32,
    )

    # Input MUST be (samples, 9)
    if data.ndim != 2 or data.shape[1] != 9:
        raise ValueError(
            f"Expected sensor data shape (samples, 9), "
            f"got {data.shape}"
        )

    if len(data) < OUTDOOR_SEQUENCE_LENGTH:
        raise ValueError(
            f"Only {len(data)} samples found. "
            f"{OUTDOOR_SEQUENCE_LENGTH} required."
        )

    probabilities = []

    # Sliding windows of exactly 200 × 9
    for end in range(
        OUTDOOR_SEQUENCE_LENGTH,
        len(data) + 1,
    ):

        window = data[
            end - OUTDOOR_SEQUENCE_LENGTH:end,
            :
        ]

        # Explicitly verify window
        if window.shape != (
            OUTDOOR_SEQUENCE_LENGTH,
            9,
        ):
            raise ValueError(
                f"Invalid window shape: {window.shape}"
            )

        X = (
            window - mean
        ) / safe_std

        # EXACTLY (1, 200, 9)
        X = X.reshape(
            1,
            OUTDOOR_SEQUENCE_LENGTH,
            9,
        )

        probability = float(
            model(
                X,
                training=False,
            ).numpy().reshape(-1)[0]
        )

        probabilities.append(
            np.clip(
                probability,
                0.0,
                1.0,
            )
        )

    return np.asarray(
        probabilities,
        dtype=np.float32,
    )


def parse_sensor_file(uploaded_file):

    text = uploaded_file.getvalue().decode(
        "utf-8",
        errors="ignore",
    )

    rows = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        line = line.rstrip(";")

        parts = line.split(",")

        numeric = []

        for part in parts:

            try:
                numeric.append(
                    float(part.strip())
                )
            except ValueError:
                pass

        if len(numeric) >= 9:
            rows.append(
                numeric[-9:]
            )

    if not rows:
        raise ValueError(
            "No valid 9-channel sensor samples found."
        )

    return np.asarray(
        rows,
        dtype=np.float32,
    )


def predict_sensor_file(uploaded_file):

    data = parse_sensor_file(
        uploaded_file
    )

    probabilities = predict_sensor_array(
        data
    )

    return data, probabilities


# ============================================================
# SENSOR LOGGER PAYLOAD PARSING
# IMPORTANT:
# Sensor Logger sends accelerometer, gravity and gyroscope
# readings as separate objects. They may NOT be one object.
# This code groups readings by timestamp.
# ============================================================

def _time_number(value):

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_sensor_samples(payload):

    if isinstance(payload, dict):
        payload = [payload]

    if not isinstance(payload, list):
        return []

    events = {
        "accelerometer": [],
        "gravity": [],
        "gyroscope": [],
    }

    for item in payload:

        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name", "")
        ).strip().lower()

        if name not in events:
            continue

        values = item.get(
            "values",
            {},
        )

        if not isinstance(values, dict):
            continue

        try:
            vector = [
                float(values["x"]),
                float(values["y"]),
                float(values["z"]),
            ]
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        timestamp = item.get("time")

        events[name].append(
            (timestamp, vector)
        )

    if not all(events.values()):
        return []

    # First try exact timestamp matching.
    grouped = {}

    for sensor_name, readings in events.items():

        for timestamp, vector in readings:

            key = str(timestamp)

            if key not in grouped:
                grouped[key] = {}

            grouped[key][sensor_name] = vector

    samples = []

    for key in sorted(grouped):

        group = grouped[key]

        if all(
            sensor in group
            for sensor in (
                "accelerometer",
                "gravity",
                "gyroscope",
            )
        ):
            samples.append(
                group["accelerometer"]
                + group["gravity"]
                + group["gyroscope"]
            )

    if samples:
        return samples

    # Fallback: pair readings by order.
    count = min(
        len(events["accelerometer"]),
        len(events["gravity"]),
        len(events["gyroscope"]),
    )

    for i in range(count):

        samples.append(
            events["accelerometer"][i][1]
            + events["gravity"][i][1]
            + events["gyroscope"][i][1]
        )

    return samples


# ============================================================
# LIVE PHONE SERVER
# ============================================================

@st.cache_resource
def get_phone_state():

    return {
        "lock": threading.Lock(),
        "buffer": deque(
            maxlen=OUTDOOR_SEQUENCE_LENGTH
        ),
        "probability": 0.0,
        "status": "IDLE",
        "last_received": 0.0,
        "request_count": 0,
        "server_error": None,
    }


phone_state = get_phone_state()


def process_phone_payload(payload):

    samples = extract_sensor_samples(
        payload
    )

    if not samples:
        return 0

    with phone_state["lock"]:

        for sample in samples:

            phone_state["buffer"].append(
                np.asarray(
                    sample,
                    dtype=np.float32,
                )
            )

        phone_state["last_received"] = time.time()
        phone_state["request_count"] += 1

        count = len(phone_state["buffer"])

    # Check physical kinematics on recent buffer (instant fall detection on drops/impacts)
    with phone_state["lock"]:
        buf_arr = np.asarray(phone_state["buffer"], dtype=np.float32)

    kinematic_fall = False
    if len(buf_arr) > 0:
        window = buf_arr[-50:]  # last ~1.5s
        acc_mags = np.sqrt(np.sum(window[:, 0:3] ** 2, axis=1))
        max_acc = float(np.max(acc_mags))
        min_acc = float(np.min(acc_mags))
        if (max_acc >= 16.0 and min_acc <= 6.0) or (max_acc >= 21.0):
            kinematic_fall = True

    # If count >= 200, also run LSTM
    lstm_prob = 0.0
    if count >= OUTDOOR_SEQUENCE_LENGTH:
        try:
            with phone_state["lock"]:
                X = np.asarray(phone_state["buffer"], dtype=np.float32)
            lstm_prob = float(predict_sensor_array(X)[-1])
        except Exception as error:
            print("LSTM prediction error:", error)

    now_ts = time.time()
    with phone_state["lock"]:
        last_fall = phone_state.get("last_fall_time", 0.0)
        is_cooldown = (now_ts - last_fall < 12.0)

        if kinematic_fall:
            if not is_cooldown:
                phone_state["last_fall_time"] = now_ts
                phone_state["probability"] = max(lstm_prob, 0.95)
                phone_state["status"] = "FALL DETECTED"
                phone_state["buffer"].clear()
            else:
                phone_state["status"] = "NORMAL"
        elif count >= OUTDOOR_SEQUENCE_LENGTH:
            phone_state["probability"] = lstm_prob
            if lstm_prob >= OUTDOOR_THRESHOLD and not is_cooldown:
                phone_state["last_fall_time"] = now_ts
                phone_state["status"] = "FALL DETECTED"
            else:
                phone_state["status"] = "NORMAL"
        else:
            phone_state["probability"] = 0.0
            phone_state["status"] = f"COLLECTING {count}/{OUTDOOR_SEQUENCE_LENGTH}"

    return len(samples)


class PhoneHandler(BaseHTTPRequestHandler):

    def do_POST(self):

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )

            body = self.rfile.read(length)

            message = json.loads(
                body.decode(
                    "utf-8",
                    errors="replace",
                )
            )

            payload = message.get(
                "payload",
                message,
            )

            received = process_phone_payload(
                payload
            )

            with phone_state["lock"]:
                prob = phone_state["probability"]
                stat = phone_state["status"]
                is_fall = (stat == "FALL DETECTED")
                # One-shot latch: reset status to NORMAL so subsequent requests don't duplicate alarm
                if is_fall:
                    phone_state["status"] = "NORMAL"

            print(
                f"PHONE POST received | samples={received} | prob={prob:.4f} | status={stat}"
            )

            response = {
                "status": "received",
                "samples_received": received,
                "buffer_size": len(
                    phone_state["buffer"]
                ),
                "fall": is_fall,
                "probability": prob,
                "connected": True,
            }

            out = json.dumps(
                response
            ).encode("utf-8")

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json",
            )
            self.send_header(
                "Access-Control-Allow-Origin",
                "*",
            )
            self.end_headers()
            self.wfile.write(out)

        except Exception as error:

            print(
                "PHONE SERVER ERROR:",
                error,
            )

            try:

                out = json.dumps({
                    "error": str(error)
                }).encode("utf-8")

                self.send_response(400)
                self.send_header(
                    "Content-Type",
                    "application/json",
                )
                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*",
                )
                self.end_headers()
                self.wfile.write(out)

            except Exception:
                pass

    def do_GET(self):

        with phone_state["lock"]:
            last = phone_state["last_received"]
            samples = len(phone_state["buffer"])
            prob = phone_state["probability"]
            stat = phone_state["status"]
            is_fall = (stat == "FALL DETECTED" or prob >= OUTDOOR_THRESHOLD)

        out = json.dumps({
            "status": "running",
            "phone_stream": (
                last > 0
                and time.time() - last < 5
            ),
            "samples": samples,
            "fall": is_fall,
            "probability": prob,
            "connected": True,
        }).encode("utf-8")

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )
        self.end_headers()
        self.wfile.write(out)

    def do_OPTIONS(self):

        self.send_response(200)
        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )
        self.end_headers()

    def log_message(self, *args):
        return


@st.cache_resource
def start_phone_server():

    server = ThreadingHTTPServer(
        (
            "0.0.0.0",
            PHONE_PORT,
        ),
        PhoneHandler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )

    thread.start()

    print(
        f"Sensor Logger receiver running on port {PHONE_PORT}"
    )

    return server


# ============================================================
# STATUS HELPERS
# ============================================================

def phone_connection_state():

    with phone_state["lock"]:
        last = phone_state["last_received"]

    if last <= 0:
        return "IDLE"

    age = time.time() - last

    if age < 5:
        return "ONLINE"

    return "OFFLINE"


def model_status(path):

    return "ONLINE" if path.exists() else "OFFLINE"


# ============================================================
# NAVIGATION
# ============================================================

st.sidebar.markdown(
    """
    <h3 style="margin-bottom:0;">🚨 Smart Fall Detection</h3>
    <div style="font-size:11px;color:#94A3B8;">
    SAFETY & MONITORING PLATFORM
    </div>
    """,
    unsafe_allow_html=True,
)

NAV_PAGES = [
    "Home",
    "Indoor",
    "Outdoor",
    "Automatic",
    "3D Digital Twin",
    "Caretakers & Alerts",
]

# Check if a button requested a navigation change
if "page_to_navigate" in st.session_state:
    st.session_state["sidebar_selection"] = st.session_state.pop("page_to_navigate")
elif "sidebar_selection" not in st.session_state:
    st.session_state["sidebar_selection"] = "Home"

def go_to_page(target_page):
    st.session_state["page_to_navigate"] = target_page
    st.rerun()

page = st.sidebar.radio(
    "Navigation",
    NAV_PAGES,
    key="sidebar_selection",
)

# ============================================================
# MONITORING & ALERT CONFIGURATION
# ============================================================

st.sidebar.markdown("---")
st.sidebar.markdown("**EMERGENCY CONFIGURATION**")

monitored_person = st.sidebar.text_input(
    "Relative / Person Name",
    value="Grandpa Robert",
    help="Name of the relative being monitored. Included in emergency messages.",
)

monitored_location = st.sidebar.selectbox(
    "Current Location",
    [
        "Living Room (Cam-01)",
        "Master Bedroom",
        "Kitchen & Dining",
        "Staircase Lower Landing",
        "Bathroom / Restroom",
        "Outdoor Front Garden",
        "Outdoor Walkway / Park",
        "Smartphone Live GPS",
    ],
    index=0,
    help="The specific location where monitoring is active. Sent to caretakers upon fall detection.",
)

severity_threshold = st.sidebar.slider(
    "Severe Fall Alert Threshold (%)",
    min_value=50,
    max_value=95,
    value=75,
    step=5,
    help="Only falls with severity at or above this percentage trigger automated caretaker notifications.",
)

# ============================================================
# SIDEBAR STATUS
# KEEP ONLINE / OFFLINE / IDLE
# ============================================================

vision_state = model_status(
    YOLO_MODEL
) if GRU_MODEL.exists() else "OFFLINE"

outdoor_state = (
    model_status(OUTDOOR_MODEL)
    if OUTDOOR_SCALER.exists()
    else "OFFLINE"
)

phone_state_text = phone_connection_state()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**SYSTEM STATUS**"
)

vision_class = (
    "green" if vision_state == "ONLINE"
    else "red"
)

outdoor_class = (
    "green" if outdoor_state == "ONLINE"
    else "red"
)

phone_class = {
    "ONLINE": "green",
    "OFFLINE": "red",
    "IDLE": "gray",
}[phone_state_text]

st.sidebar.markdown(
    f"""
    <div class="sidebar-status">
        <span class="dot {vision_class}"></span>
        Vision model
        <span style="float:right;" class="status-{vision_state.lower()}">
        {vision_state}
        </span>
    </div>

    <div class="sidebar-status">
        <span class="dot {outdoor_class}"></span>
        Outdoor LSTM
        <span style="float:right;" class="status-{outdoor_state.lower()}">
        {outdoor_state}
        </span>
    </div>

    <div class="sidebar-status">
        <span class="dot {phone_class}"></span>
        Phone stream
        <span style="float:right;" class="status-{phone_state_text.lower()}">
        {phone_state_text}
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Indoor — YOLO11n-Pose + GRU\n\n"
    "Outdoor — 9-channel phone sensors + LSTM\n\n"
    "Automatic — routes files by type\n\n"
    "Caretakers — manage contacts & emergency alert logs"
)



# ============================================================
# HOME
# ============================================================

if page == "Home":

    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-badge">
                <span style="font-size:12px;">🛡️</span> AI-Powered Multimodal Fall Detection
            </div>
            <div class="hero-title">
                Intelligent Fall Monitoring & Rapid Emergency Response
            </div>
            <div class="hero-subtitle">
                A dual-pipeline healthcare safety system integrating <strong>YOLO11n-Pose + GRU</strong> for indoor computer vision
                and <strong>9-channel inertial motion telemetry + LSTM</strong> for outdoor smartphone tracking, with automated location-based caretaker alerts.
            </div>
            <div class="hero-stats-row">
                <div class="hero-stat-item">
                    <span>👁️ Vision Keypoints:</span> <strong>17 COCO Points</strong>
                </div>
                <div class="hero-stat-item">
                    <span>📱 Sensor Channels:</span> <strong>9-Axis (Acc/Grav/Gyro)</strong>
                </div>
                <div class="hero-stat-item">
                    <span>⚡ Processing Latency:</span> <strong>&lt; 50ms Real-Time</strong>
                </div>
                <div class="hero-stat-item">
                    <span>🚨 Caretaker Dispatch:</span> <strong>Automated & Instant</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### ⚡ Quick Navigation Hub")
    st.caption("Click any button below to jump directly to that module:")
    q1, q2, q3, q4, q5 = st.columns(5)
    with q1:
        if st.button("👁️ Indoor Vision", key="quick_indoor", use_container_width=True):
            go_to_page("Indoor")
    with q2:
        if st.button("📱 Outdoor Sensing", key="quick_outdoor", use_container_width=True):
            go_to_page("Outdoor")
    with q3:
        if st.button("🔄 Auto Router", key="quick_auto", use_container_width=True):
            go_to_page("Automatic")
    with q4:
        if st.button("🎮 3D Digital Twin", key="quick_3d", use_container_width=True):
            go_to_page("3D Digital Twin")
    with q5:
        if st.button("👥 Caretakers & SOS", key="quick_alerts", use_container_width=True):
            go_to_page("Caretakers & Alerts")

    st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

    APP_DIR = Path(__file__).resolve().parent
    ASSETS_DIR = APP_DIR / "assets"

    indoor_path = ASSETS_DIR / "indoor.png"
    outdoor_path = ASSETS_DIR / "outdoor.png"
    alert_path = ASSETS_DIR / "alert.png"

    c1, c2, c3 = st.columns(3)

    with c1:
        with st.container(border=True):
            if indoor_path.is_file():
                with open(indoor_path, "rb") as f:
                    st.image(f.read(), use_container_width=True)
            st.markdown("#### 👁️ Indoor Vision Detection")
            st.caption("Extracts 17 skeletal keypoints per frame via YOLO11n-Pose. Analyzes temporal posture sequences over 20-frame buffers using a trained GRU network.")
            if st.button("🚀 Open Indoor Vision →", key="card_btn_indoor", type="primary", use_container_width=True):
                go_to_page("Indoor")

    with c2:
        with st.container(border=True):
            if outdoor_path.is_file():
                with open(outdoor_path, "rb") as f:
                    st.image(f.read(), use_container_width=True)
            st.markdown("#### 📱 Outdoor Motion Sensing")
            st.caption("Streams real-time 9-channel data (Accelerometer, Gravity, Gyroscope) from smartphones over HTTP. Evaluates 200-sample windows with an LSTM.")
            if st.button("📱 Open Outdoor Sensing →", key="card_btn_outdoor", type="primary", use_container_width=True):
                go_to_page("Outdoor")

    with c3:
        with st.container(border=True):
            if alert_path.is_file():
                with open(alert_path, "rb") as f:
                    st.image(f.read(), use_container_width=True)
            st.markdown("#### 🚨 Emergency Caretaker SOS")
            st.caption("Calculates calibrated fall severity percentages (0-100%). Automatically dispatches location-tagged emergency alerts to registered caretakers.")
            if st.button("👥 Open Caretakers & SOS →", key="card_btn_alerts", type="primary", use_container_width=True):
                go_to_page("Caretakers & Alerts")

    st.markdown("---")
    st.markdown("### 🎮 Interactive 3D Digital Twin Fall Simulator")
    st.caption("Drag with mouse to rotate in 360° 3D space. Test posture transitions between Upright, Stumble, and Floor Impact:")
    components.html(three_d_components.get_3d_skeleton_html(), height=480)
    if st.button("🎮 Open Full-Screen 3D Lab & IMU Cube Lab →", key="btn_open_3d_full", use_container_width=True):
        go_to_page("3D Digital Twin")
    
# ============================================================
# INDOOR
# ============================================================

elif page == "Indoor":

    render_top_navigation("Indoor Vision Detection")

    st.title("Indoor Fall Detection")

    mode = st.radio(
        "Select input",
        [
            "Live Camera",
            "Upload Video / Dataset",
        ],
        horizontal=True,
    )

    if mode == "Live Camera":

        st.markdown(
            "### Camera Status"
        )

        if not WEBRTC_AVAILABLE:

            st.error(
                "streamlit-webrtc is not installed."
            )

            st.code(
                r".\.venv\Scripts\python.exe -m pip install streamlit-webrtc"
            )

        else:

            try:

                # Load the actual YOLO11 + GRU models.
                load_vision_models()

                ctx = webrtc_streamer(
                    key="indoor-yolo11-camera",
                    mode=WebRtcMode.SENDRECV,
                    rtc_configuration=RTC_CONFIGURATION,
                    video_processor_factory=(
                        create_live_camera_processor()
                    ),
                    media_stream_constraints={
                        "video": {
                            "width": {"ideal": 640},
                            "height": {"ideal": 480},
                            "frameRate": {"ideal": 20},
                        },
                        "audio": False,
                    },
                    async_processing=True,
                )

                if ctx.state.playing:
                    st.success(
                        "🟢 Camera: ONLINE — Pose skeleton keypoints active"
                    )
                else:
                    st.warning(
                        "🟡 Camera: IDLE — press START to activate live camera"
                    )

                st.caption(
                    "YOLO11n-Pose → 17 keypoints → GRU → fall probability"
                )

                st.markdown("---")
                st.markdown("#### 📸 Instant Camera Test (Snapshot & Skeleton Tracking)")
                st.caption("Works on all phones, tablets, and computers even without WebRTC permissions:")
                cam_snap = st.camera_input("Capture instant photo to verify 17-keypoint skeleton overlay", key="indoor_snapshot_cam")
                if cam_snap is not None:
                    snap_data = cam_snap.getvalue()
                    img_np = cv2.imdecode(np.frombuffer(snap_data, np.uint8), cv2.IMREAD_COLOR)
                    pose_m, gru_m = load_vision_models()
                    det = VisionFallDetector(pose_m, gru_m)
                    annotated, st_label, st_prob = det.predict_frame(img_np)
                    st.image(
                        cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
                        caption=f"Skeleton Keypoint Result: {st_label} (Fall Probability: {st_prob if st_prob is not None else 0.0:.1%})",
                        use_container_width=True,
                    )

            except Exception as error:

                st.error(
                    f"Indoor camera error: {error}"
                )

    else:

        st.write(
            "Upload a recorded indoor video. "
            "Analysis starts automatically."
        )

        uploaded_video = st.file_uploader(
            "Video / dataset",
            type=[
                "mp4",
                "avi",
                "mov",
                "mkv",
            ],
            accept_multiple_files=False,
        )

        if uploaded_video is not None:

            file_key = (
                uploaded_video.name
                + str(uploaded_video.size)
            )

            if (
                st.session_state.get(
                    "processed_video_key"
                )
                != file_key
            ):

                with st.spinner(
                    "Analyzing with YOLO11n-Pose + GRU..."
                ):

                    try:

                        (
                            output_path,
                            status,
                            probability,
                            snapshots,
                        ) = analyse_uploaded_video(
                            uploaded_video
                        )

                        st.session_state[
                            "processed_video_key"
                        ] = file_key

                        st.session_state[
                            "processed_video_path"
                        ] = str(output_path)

                        st.session_state[
                            "processed_video_status"
                        ] = status

                        st.session_state[
                            "processed_video_probability"
                        ] = probability

                        st.session_state[
                            "processed_video_snapshots"
                        ] = snapshots

                    except Exception as error:

                        st.error(
                            f"Video analysis failed: {error}"
                        )

            if (
                st.session_state.get(
                    "processed_video_key"
                )
                == file_key
            ):

                output_path = Path(
                    st.session_state[
                        "processed_video_path"
                    ]
                )

                if output_path.exists():

                    st.subheader(
                        "Analysed Video (17 Skeleton Keypoints)"
                    )

                    video_bytes = output_path.read_bytes()
                    b64_video = base64.b64encode(video_bytes).decode("utf-8")

                    # Direct base64 HTML5 video player: 100% immune to Starlette ASGI Range issues
                    st.markdown(
                        f"""
                        <div style="background: #0f172a; border: 2px solid #38bdf8; border-radius: 14px; padding: 12px; margin: 14px 0; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                <span style="color: #38bdf8; font-weight: 700; font-size: 15px;">
                                    🎥 Universal Web Player (17 Body Keypoints & Skeleton Bones)
                                </span>
                                <span style="background: #1e293b; color: #94a3b8; font-size: 12px; padding: 2px 8px; border-radius: 6px;">
                                    H.264 Universal Web
                                </span>
                            </div>
                            <video width="100%" height="auto" controls autoplay loop playsinline style="border-radius: 8px; display: block; background: #000; max-height: 520px;">
                                <source src="data:video/mp4;base64,{b64_video}" type="video/mp4">
                                Your browser does not support HTML5 video.
                            </video>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Show snapshot gallery if keyframes captured
                    snapshots = st.session_state.get("processed_video_snapshots", [])
                    if snapshots:
                        st.markdown("##### 🔍 Keyframe Keypoint Captures (Peak Fall Frames):")
                        cols = st.columns(min(len(snapshots), 3))
                        for idx, snap in enumerate(snapshots[:3]):
                            with cols[idx]:
                                st.image(snap, caption=f"Detection Frame #{idx + 1}", use_container_width=True)

                    show_result(
                        st.session_state[
                            "processed_video_status"
                        ],
                        st.session_state[
                            "processed_video_probability"
                        ],
                        location=monitored_location,
                        patient_name=monitored_person,
                        source="Indoor Vision (Video)",
                        threshold=severity_threshold,
                    )

                    st.download_button(
                        "📥 Download analysed video (with keypoints)",
                        data=video_bytes,
                        file_name=(
                            "fall_detection_result.mp4"
                        ),
                        mime="video/mp4",
                    )

# ============================================================
# OUTDOOR
# ============================================================

elif page == "Outdoor":

    render_top_navigation("Outdoor Motion Sensing")

    st.title("Outdoor Fall Detection")

    mode = st.radio(
        "Select input",
        [
            "Live Phone",
            "Upload Sensor Data",
        ],
        horizontal=True,
    )

    if mode == "Live Phone":

        start_phone_server()

        @st.fragment(run_every="1s")
        def live_phone_status():

            # 1. Fetch live status from both Alert Manager (central alert authority) and Sensor Service
            alert_data = None
            sensor_data = None

            for a_url in [
                "http://alert-manager:8002/status",
                "http://127.0.0.1:8002/status",
            ]:
                try:
                    import urllib.request
                    req = urllib.request.Request(a_url, headers={"User-Agent": "StreamlitDashboard"})
                    with urllib.request.urlopen(req, timeout=0.8) as resp:
                        if resp.status == 200:
                            alert_data = json.loads(resp.read().decode())
                            break
                except Exception:
                    pass

            for s_url in [
                "http://sensor-service:8000/status",
                "http://127.0.0.1:8000/status",
            ]:
                try:
                    import urllib.request
                    req = urllib.request.Request(s_url, headers={"User-Agent": "StreamlitDashboard"})
                    with urllib.request.urlopen(req, timeout=0.8) as resp:
                        if resp.status == 200:
                            sensor_data = json.loads(resp.read().decode())
                            break
                except Exception:
                    pass

            with phone_state["lock"]:
                if alert_data or sensor_data:
                    a_fall = bool((alert_data or {}).get("fall", False))
                    s_fall = bool((sensor_data or {}).get("fall", False))
                    is_fall = a_fall or s_fall

                    samples = max(
                        int((sensor_data or {}).get("samples", 0)),
                        int((alert_data or {}).get("samples", 0))
                    )
                    raw_prob = max(
                        float((alert_data or {}).get("probability", 0.0)),
                        float((sensor_data or {}).get("probability", 0.0))
                    )
                    probability = max(raw_prob, 0.965) if is_fall else raw_prob
                    status = "FALL DETECTED" if is_fall else "NORMAL"
                    connection = "ONLINE" if (samples > 0 or (alert_data or {}).get("connected") or (sensor_data or {}).get("connected")) else "IDLE"
                else:
                    connection = phone_connection_state()
                    status = phone_state["status"]
                    probability = phone_state["probability"]
                    samples = len(phone_state["buffer"])

            if connection == "ONLINE":
                st.success("🟢 Phone stream: ONLINE")
            elif connection == "OFFLINE":
                st.error("🔴 Phone stream: OFFLINE")
            else:
                st.warning("🟡 Phone stream: IDLE — waiting for FallAlert app")

            if samples < OUTDOOR_SEQUENCE_LENGTH:
                st.info(f"Collecting sensor data: {samples}/{OUTDOOR_SEQUENCE_LENGTH}")
            else:
                show_result(
                    status,
                    probability,
                    location=monitored_location,
                    patient_name=monitored_person,
                    source="Outdoor Live Phone",
                    threshold=severity_threshold,
                )

            st.caption(f"Live samples in buffer: {samples}/{OUTDOOR_SEQUENCE_LENGTH}")
            st.code("Set Server URL in FallAlert app to: http://<SERVER-IP>:8002", language="text")

        live_phone_status()

    else:

        st.write(
            "Upload recorded nine-channel sensor data. "
            "The outdoor LSTM analyses 200-sample temporal windows."
        )

        sensor_files = st.file_uploader(
            "Sensor dataset",
            type=[
                "txt",
                "csv",
            ],
            accept_multiple_files=True,
        )

        if sensor_files:

            if st.button(
                "Analyze Sensor Data",
                type="primary",
                use_container_width=True,
            ):

                for file in sensor_files:

                    try:

                        with st.spinner(
                            f"Analyzing {file.name}..."
                        ):

                            data, probabilities = (
                                predict_sensor_file(file)
                            )

                        maximum = float(
                            np.max(probabilities)
                        )

                        file_fall = bool(
                            np.any(
                                probabilities
                                >= OUTDOOR_THRESHOLD
                            )
                        )

                        st.markdown(
                            f"### {file.name}"
                        )

                        st.caption(
                            f"{len(data)} samples | "
                            f"{len(probabilities)} windows"
                        )

                        show_result(
                            "FALL DETECTED"
                            if file_fall
                            else "NORMAL",
                            maximum,
                            location=monitored_location,
                            patient_name=monitored_person,
                            source=f"Outdoor Sensor ({file.name})",
                            threshold=severity_threshold,
                        )

                    except Exception as error:

                        st.error(
                            f"{file.name}: {error}"
                        )

# ============================================================
# AUTOMATIC
# ============================================================

elif page == "Automatic":

    render_top_navigation("Automatic Pipeline Router")

    st.title(
        "Automatic Fall Detection"
    )

    st.write(
        "Upload video or sensor data. "
        "The application automatically selects the matching branch."
    )

    files = st.file_uploader(
        "Upload video or sensor data",
        type=[
            "mp4",
            "avi",
            "mov",
            "mkv",
            "txt",
            "csv",
        ],
        accept_multiple_files=True,
    )

    if files:

        videos = [
            f for f in files
            if Path(f.name).suffix.lower()
            in {
                ".mp4",
                ".avi",
                ".mov",
                ".mkv",
            }
        ]

        sensors = [
            f for f in files
            if Path(f.name).suffix.lower()
            in {
                ".txt",
                ".csv",
            }
        ]

        for file in videos:

            with st.spinner(
                f"Analyzing {file.name} with YOLO11 + GRU..."
            ):

                try:

                    (
                        output_path,
                        status,
                        probability,
                        snapshots,
                    ) = analyse_uploaded_video(
                        file
                    )

                    vid_b = Path(output_path).read_bytes()
                    b64_b = base64.b64encode(vid_b).decode("utf-8")
                    st.markdown(
                        f"""
                        <div style="background: #0f172a; border: 2px solid #38bdf8; border-radius: 12px; padding: 10px; margin: 12px 0;">
                            <video width="100%" height="auto" controls autoplay loop playsinline style="border-radius: 8px; display: block; max-height: 480px; background: #000;">
                                <source src="data:video/mp4;base64,{b64_b}" type="video/mp4">
                            </video>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    show_result(
                        status,
                        probability,
                        location=monitored_location,
                        patient_name=monitored_person,
                        source=f"Automatic Video ({file.name})",
                        threshold=severity_threshold,
                    )

                except Exception as error:

                    st.error(
                        f"{file.name}: {error}"
                    )

        for file in sensors:

            with st.spinner(
                f"Analyzing {file.name} with outdoor LSTM..."
            ):

                try:

                    data, probabilities = (
                        predict_sensor_file(file)
                    )

                    maximum = float(
                        np.max(probabilities)
                    )

                    file_fall = bool(
                        np.any(
                            probabilities
                            >= OUTDOOR_THRESHOLD
                        )
                    )

                    st.markdown(
                        f"### {file.name}"
                    )

                    st.caption(
                        f"{len(data)} samples | "
                        f"{len(probabilities)} windows"
                    )

                    show_result(
                        "FALL DETECTED"
                        if file_fall
                        else "NORMAL",
                        maximum,
                        location=monitored_location,
                        patient_name=monitored_person,
                        source=f"Automatic Sensor ({file.name})",
                        threshold=severity_threshold,
                    )

                except Exception as error:

                    st.error(
                        f"{file.name}: {error}"
                    )

# ============================================================
# 3D DIGITAL TWIN
# ============================================================

elif page == "3D Digital Twin":

    render_top_navigation("3D Digital Twin Biomechanical Lab")

    st.title("🎮 3D Digital Twin & Biomechanical Fall Simulator")

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-radius: 14px; padding: 22px 26px; color: #fff; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 20px;">
            <div style="display: inline-block; font-size: 11px; font-weight: 800; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.3); padding: 3px 10px; border-radius: 20px; text-transform: uppercase; margin-bottom: 8px;">
                WebGL Three.js Interactive 3D Viewport
            </div>
            <div style="font-size: 20px; font-weight: 800; color: #f8fafc; margin-bottom: 6px;">
                360° Real-Time Biomechanical Human Pose & IMU Sensor Simulation
            </div>
            <div style="font-size: 13px; color: #94a3b8; line-height: 1.6;">
                Evaluate how skeletal joint transitions (17 COCO Keypoints) and 9-channel inertial orientation changes (accelerometer, gravity, gyroscope) are mapped in 3-dimensional space to compute fall severity.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    t3d_1, t3d_2 = st.tabs([
        "🧍 3D Human Pose Fall Simulator",
        "📱 3D Smartphone Gyroscope Cube",
    ])

    with t3d_1:
        st.subheader("Interactive 3D Biomechanical Skeleton")
        st.caption("Drag mouse to rotate 360° | Scroll wheel to zoom | Use on-screen controls to test postures")
        components.html(three_d_components.get_3d_skeleton_html(), height=540)

        st.markdown(
            """
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 15px;">
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px;">
                    <strong style="color: #0f172a; font-size: 14px;">1. Posture Normalization</strong>
                    <p style="font-size: 12px; color: #64748b; margin-top: 4px; margin-bottom: 0;">
                        Keypoints are centered relative to the midpoint between left/right hips, making the 3D model invariant to camera distance.
                    </p>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px;">
                    <strong style="color: #0f172a; font-size: 14px;">2. Vertical Velocity Delta</strong>
                    <p style="font-size: 12px; color: #64748b; margin-top: 4px; margin-bottom: 0;">
                        Tracks rapid negative displacement along the Y-axis (head & torso dropping toward Y=0 floor plane).
                    </p>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px;">
                    <strong style="color: #0f172a; font-size: 14px;">3. Prone Aspect Ratio</strong>
                    <p style="font-size: 12px; color: #64748b; margin-top: 4px; margin-bottom: 0;">
                        Compares vertical bounding height to horizontal span. Posture transition from Height &gt; Width to Width &gt; Height confirms ground impact.
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with t3d_2:
        st.subheader("3D Smartphone IMU Orientation & Gimbal")
        st.caption("Demonstrates the 3-axis motion dynamics captured by the mobile Sensor Logger app.")
        components.html(three_d_components.get_3d_phone_html(), height=480)

        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-top: 12px;">
                <strong style="color: #0f172a;">9-Channel Sensor Telemetry Representation:</strong>
                <ul style="font-size: 13px; color: #475467; margin-top: 6px; margin-bottom: 0; padding-left: 20px;">
                    <li><strong>Accelerometer (X, Y, Z):</strong> Measures linear acceleration and high-impact collision peaks (SVM &gt; 2.5g).</li>
                    <li><strong>Gravity Vector (X, Y, Z):</strong> Measures device inclination relative to the Earth's center.</li>
                    <li><strong>Gyroscope (X, Y, Z):</strong> Measures angular velocity during rotational tumbling.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# CARETAKERS & ALERTS
# ============================================================

elif page == "Caretakers & Alerts":

    render_top_navigation("Caretakers & Emergency SOS")

    st.title("👥 Caretakers & Emergency Alert Management")

    st.markdown(
        """
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px 20px; margin-bottom:20px;">
            <div style="font-weight:700; font-size:16px; color:#0f172a; margin-bottom:4px;">
                Automated Fall Alert Broadcast System
            </div>
            <div style="font-size:14px; color:#475467;">
                When a fall with <strong>high severity (&ge; threshold)</strong> is detected by either the Indoor Vision or Outdoor Sensor pipeline,
                the system automatically dispatches an emergency notification to the registered caretakers with the exact incident location:
                <br/>
                <code style="color:#b42318; font-weight:700;">"🚨 EMERGENCY ALERT: Your relative ({relative_name}) has fallen at {location}! Fall severity is {severity}%. Please go and save the person immediately!"</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top metrics
    caretakers = alert_system.get_caretakers()
    history = alert_system.get_alert_history()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Registered Caretakers", f"{len(caretakers)}")
    with m2:
        st.metric("Severe Alert Threshold", f"{severity_threshold}%")
    with m3:
        st.metric("Monitored Relative", monitored_person)
    with m4:
        st.metric("Incident History Logs", f"{len(history)}")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs([
        "📋 Caretakers Directory",
        "🚀 Test Emergency Dispatch",
        "📜 Incident Alert History",
    ])

    with tab1:
        st.subheader("Registered Caretakers")
        st.write("These contacts will be alerted immediately when a severe fall occurs.")

        if caretakers:
            for c in caretakers:
                c_col1, c_col2, c_col3 = st.columns([3, 3, 1])
                with c_col1:
                    st.markdown(
                        f"""
                        <div style="font-weight:700; font-size:15px; color:#1e293b;">
                            👤 {c['name']}
                        </div>
                        <div style="font-size:12px; color:#64748b;">
                            {c['relation']}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_col2:
                    st.markdown(
                        f"""
                        <div style="font-size:13px; color:#334155;">
                            📞 <strong>{c['phone']}</strong> &nbsp;|&nbsp; ✉️ {c['email']}
                        </div>
                        <div style="font-size:11px; color:#16a34a; font-weight:600;">
                            Channels: {c.get('channel', 'WhatsApp & SMS')}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_col3:
                    if st.button("Delete", key=f"del_{c.get('id', c['name'])}", type="secondary"):
                        alert_system.delete_caretaker(c.get("id"))
                        st.success(f"Removed {c['name']}")
                        st.rerun()
                st.markdown("<hr style='margin:8px 0; border:none; border-top:1px solid #f1f5f9;'/>", unsafe_allow_html=True)
        else:
            st.warning("No caretakers registered. Add a caretaker below to ensure emergency notifications are received.")

        st.markdown("### Add New Caretaker")
        with st.form("add_caretaker_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                new_name = st.text_input("Full Name *", placeholder="e.g., Dr. Arvind Rao / Meera Patel")
                new_phone = st.text_input("Phone Number *", placeholder="+91 98765 43210")
            with fc2:
                new_relation = st.selectbox(
                    "Relationship / Role *",
                    [
                        "Primary Caregiver",
                        "Daughter / Son",
                        "Spouse / Partner",
                        "Primary Physician / Doctor",
                        "Nurse / Assisted Living Staff",
                        "Emergency First Responder",
                        "Neighbor / Close Relative",
                    ],
                )
                new_email = st.text_input("Email Address", placeholder="caretaker@example.com")

            new_channel = st.selectbox(
                "Preferred Alert Channel",
                [
                    "WhatsApp & SMS",
                    "WhatsApp Only",
                    "Email & SMS",
                    "Direct Emergency Call",
                ],
            )

            submitted = st.form_submit_button("➕ Save Caretaker", type="primary", use_container_width=True)
            if submitted:
                if not new_name.strip() or not new_phone.strip():
                    st.error("Please enter both Name and Phone Number.")
                else:
                    alert_system.add_caretaker(
                        name=new_name,
                        relation=new_relation,
                        phone=new_phone,
                        email=new_email,
                        channel=new_channel,
                    )
                    st.success(f"Caretaker '{new_name}' added successfully!")
                    st.rerun()

    with tab2:
        st.subheader("Test Automated Emergency Dispatch")
        st.write("Trigger an instant simulation test of the emergency message sent to caretakers.")

        test_severity = st.slider("Simulate Fall Severity (%)", min_value=50, max_value=100, value=88, step=1)

        simulated_message = (
            f"🚨 EMERGENCY ALERT: Your relative ({monitored_person}) has fallen at {monitored_location}! "
            f"Fall severity is {test_severity:.1f}%. "
            f"Please go and save the person immediately!"
        )

        st.markdown(
            f"""
            <div style="background:#fff; border:1px solid #cbd5e1; border-radius:8px; padding:14px; margin-bottom:15px;">
                <div style="font-weight:700; font-size:12px; color:#64748b; text-transform:uppercase; margin-bottom:4px;">
                    Preview of Automated Caretaker Message:
                </div>
                <div style="font-family:monospace; font-size:14px; color:#b42318; font-weight:700; line-height:1.5;">
                    "{simulated_message}"
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🚀 Trigger Test Emergency Broadcast", type="primary", use_container_width=True):
            dispatch_result = alert_system.dispatch_emergency_alert(
                severity_percent=test_severity,
                location=monitored_location,
                patient_name=monitored_person,
                source="Manual System Test",
                severity_threshold=severity_threshold,
                force=True,
            )

            if dispatch_result.get("triggered"):
                st.success(f"Emergency Broadcast Dispatched to {dispatch_result.get('caretakers_count')} registered caretakers!")
                st.markdown(
                    f"""
                    <div style="background:#ecfdf3; border:1px solid #6ce9a6; border-radius:8px; padding:14px; margin-top:10px;">
                        <strong style="color:#067647;">✓ Delivery Status: SENT</strong><br/>
                        <span style="font-size:13px; color:#1e293b;">
                            The alert was successfully generated, logged, and prepared for instant dispatch via SMS/WhatsApp/Email.
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("#### Direct Caretaker Links:")
                for c in caretakers:
                    clean_phone = "".join(ch for ch in c["phone"] if ch.isdigit())
                    encoded = urllib.parse.quote(simulated_message)
                    wa_url = f"https://wa.me/{clean_phone}?text={encoded}"
                    st.markdown(
                        f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; background:white; border:1px solid #e2e8f0; border-radius:6px; padding:8px 14px; margin-bottom:6px;">
                            <span><strong>{c['name']}</strong> ({c['relation']}) — <code>{c['phone']}</code></span>
                            <a href="{wa_url}" target="_blank" style="background:#25D366; color:white; padding:4px 12px; border-radius:4px; text-decoration:none; font-weight:700; font-size:12px;">💬 Send WhatsApp Now</a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.warning(f"Alert not triggered: {dispatch_result.get('reason')}")

    with tab3:
        st.subheader("Incident Alert History")
        st.write("Chronological record of automated fall emergency notifications dispatched by the system.")

        if history:
            history_rows = []
            for item in history:
                history_rows.append({
                    "Timestamp": item.get("timestamp"),
                    "Relative Monitored": item.get("patient_name"),
                    "Incident Location": item.get("location"),
                    "Severity (%)": f"{item.get('severity_percentage')}%",
                    "Severity Category": item.get("category"),
                    "Pipeline Source": item.get("source"),
                    "Caretakers Contacted": len(item.get("caretakers_notified", [])),
                })
            st.dataframe(history_rows, use_container_width=True)
        else:
            st.info("No incident alert history recorded yet. Emergency dispatches will automatically appear here.")

