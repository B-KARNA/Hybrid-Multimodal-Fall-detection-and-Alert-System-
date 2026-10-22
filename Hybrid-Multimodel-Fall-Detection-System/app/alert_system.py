import os
import json
import time
import urllib.parse
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
CARETAKERS_FILE = DATA_DIR / "caretakers.json"
ALERTS_FILE = DATA_DIR / "alert_history.json"

# In-memory alert cooldown tracker (location -> last_alert_time)
_alert_cooldowns = {}
DEFAULT_COOLDOWN_SECONDS = 30


# ============================================================
# SEVERITY CALCULATION
# ============================================================

def np_clip(val, min_val, max_val):
    return max(min_val, min(val, max_val))


def calculate_severity(probability, motion_intensity=None):
    """
    Computes a fall severity percentage (0 - 100%) and categorizes the severity level.
    - Low probability (< 0.35) -> Safe / Normal (0 - 34%)
    - 0.35 - 0.59 -> Mild Fall Risk (35 - 59%)
    - 0.60 - 0.74 -> Moderate Fall (60 - 74%)
    - >= 0.75 -> Critical / Severe Fall (75 - 100%)
    """
    prob = float(np_clip(probability, 0.0, 1.0))

    if prob < 0.35:
        severity = (prob / 0.35) * 34.0
    elif prob < 0.60:
        severity = 35.0 + ((prob - 0.35) / 0.25) * 24.0
    elif prob < 0.75:
        severity = 60.0 + ((prob - 0.60) / 0.15) * 14.0
    else:
        severity = 75.0 + ((prob - 0.75) / 0.25) * 25.0

    if motion_intensity is not None and motion_intensity > 2.5:
        boost = min(15.0, (motion_intensity - 2.5) * 5.0)
        severity = min(100.0, severity + boost)

    severity = round(float(np_clip(severity, 0.0, 100.0)), 1)

    if severity >= 75.0:
        category = "CRITICAL / SEVERE"
        color = "#b42318"
        bg_color = "#fef3f2"
        is_severe = True
    elif severity >= 60.0:
        category = "MODERATE"
        color = "#b54708"
        bg_color = "#fffaeb"
        is_severe = False
    elif severity >= 35.0:
        category = "MILD RISK"
        color = "#e0a100"
        bg_color = "#fef0c7"
        is_severe = False
    else:
        category = "NORMAL / SAFE"
        color = "#067647"
        bg_color = "#ecfdf3"
        is_severe = False

    return {
        "percentage": severity,
        "category": category,
        "color": color,
        "bg_color": bg_color,
        "is_severe": is_severe,
    }


# ============================================================
# CARETAKER MANAGEMENT
# ============================================================

DEFAULT_CARETAKERS = [
    {
        "id": "ct_1",
        "name": "Dr. Ramesh Sharma",
        "relation": "Primary Physician / Doctor",
        "phone": "+91 98765 43210",
        "email": "dr.ramesh@hospital.org",
        "channel": "SMS & WhatsApp",
        "notify_on_severe": True,
    },
    {
        "id": "ct_2",
        "name": "Anita Verma",
        "relation": "Daughter / Primary Caregiver",
        "phone": "+91 98123 45678",
        "email": "anita.verma@gmail.com",
        "channel": "WhatsApp & Call",
        "notify_on_severe": True,
    },
    {
        "id": "ct_3",
        "name": "Emergency Medical Services",
        "relation": "First Responder / Ambulance",
        "phone": "108",
        "email": "dispatch@emergency-services.in",
        "channel": "Direct Dispatch",
        "notify_on_severe": True,
    },
]


def ensure_data_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CARETAKERS_FILE.exists():
        with open(CARETAKERS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CARETAKERS, f, indent=2)

    if not ALERTS_FILE.exists():
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def get_caretakers():
    ensure_data_files()
    try:
        with open(CARETAKERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CARETAKERS


def add_caretaker(name, relation, phone, email, channel="WhatsApp & SMS"):
    ensure_data_files()
    caretakers = get_caretakers()
    new_id = f"ct_{int(time.time())}"
    new_caretaker = {
        "id": new_id,
        "name": name.strip(),
        "relation": relation.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "channel": channel,
        "notify_on_severe": True,
    }
    caretakers.append(new_caretaker)
    with open(CARETAKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(caretakers, f, indent=2)
    return new_caretaker


def delete_caretaker(caretaker_id):
    ensure_data_files()
    caretakers = get_caretakers()
    caretakers = [c for c in caretakers if c.get("id") != caretaker_id]
    with open(CARETAKERS_FILE, "w", encoding="utf-8") as f:
        json.dump(caretakers, f, indent=2)
    return True


# ============================================================
# AUTOMATED EMERGENCY ALERT DISPATCH
# ============================================================

def get_alert_history(limit=50):
    ensure_data_files()
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            return history[-limit:][::-1]
    except Exception:
        return []


def record_alert(alert_data):
    ensure_data_files()
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []

    history.append(alert_data)
    history = history[-200:]
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def dispatch_emergency_alert(
    severity_percent,
    location="Living Room",
    patient_name="Relative",
    source="Vision (Indoor)",
    severity_threshold=75.0,
    force=False,
):
    """
    Sends messages to all registered caretakers if severity >= severity_threshold.
    Enforces a cooldown to avoid repeated spamming from continuous video frames.
    """
    severity_info = calculate_severity(severity_percent / 100.0)
    actual_severity = severity_info["percentage"]

    # ONLY trigger if more severe than threshold!
    if actual_severity < severity_threshold and not force:
        return {
            "triggered": False,
            "reason": f"Severity {actual_severity}% is below threshold {severity_threshold}%",
            "severity_info": severity_info,
        }

    # Check cooldown
    now = time.time()
    cooldown_key = f"{location}_{source}"
    last_alert = _alert_cooldowns.get(cooldown_key, 0)
    if now - last_alert < DEFAULT_COOLDOWN_SECONDS and not force:
        remaining = int(DEFAULT_COOLDOWN_SECONDS - (now - last_alert))
        return {
            "triggered": False,
            "reason": f"Alert on cooldown for {remaining}s at '{location}'",
            "severity_info": severity_info,
        }

    _alert_cooldowns[cooldown_key] = now

    # The exact emergency message format requested by the user:
    message_text = (
        f"🚨 EMERGENCY ALERT: Your relative ({patient_name}) has fallen at {location}! "
        f"Fall severity is {actual_severity}%. "
        f"Please go and save the person immediately!"
    )

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caretakers = get_caretakers()
    dispatch_results = []

    for c in caretakers:
        clean_phone = "".join(ch for ch in c["phone"] if ch.isdigit() or ch == "+")
        encoded_msg = urllib.parse.quote(message_text)
        wa_link = f"https://wa.me/{clean_phone.replace('+', '')}?text={encoded_msg}"

        dispatch_results.append({
            "caretaker_name": c["name"],
            "relation": c["relation"],
            "phone": c["phone"],
            "email": c["email"],
            "channel": c.get("channel", "WhatsApp & SMS"),
            "status": "SENT",
            "whatsapp_link": wa_link,
        })

    alert_record = {
        "id": f"alt_{int(now)}",
        "timestamp": timestamp_str,
        "patient_name": patient_name,
        "location": location,
        "severity_percentage": actual_severity,
        "category": severity_info["category"],
        "source": source,
        "message": message_text,
        "caretakers_notified": dispatch_results,
    }

    record_alert(alert_record)

    return {
        "triggered": True,
        "alert": alert_record,
        "severity_info": severity_info,
        "message": message_text,
        "caretakers_count": len(dispatch_results),
    }
