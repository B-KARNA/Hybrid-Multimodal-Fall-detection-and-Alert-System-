# Hybrid Multimodal Fall Detection and Alert System (HMFDA)

An end-to-end intelligent fall detection and emergency response ecosystem combining **computer vision (indoor)**, **smartphone inertial sensors (outdoor)**, and an **Android companion application** with automated emergency alerting, SMS dispatch, and voice calling.

---

## 🏛 System Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   DETECTION LAYER                      │
├────────────────────────────┬───────────────────────────┤
│   Indoor Vision Pipeline   │   Outdoor Sensor Pipeline │
│  • Live Camera Feed        │  • 9-Channel IMU (Acc/Gyro)│
│  • YOLO11n-Pose Extraction │  • Kinematics Drop Check  │
│  • Temporal Sequence GRU   │  • LSTM Neural Classifier │
└─────────────┬──────────────┴─────────────┬─────────────┘
              │ Confirmed Falls            │ Confirmed Falls
              ▼                            ▼
┌────────────────────────────────────────────────────────┐
│             CENTRALIZED ALERT MANAGER                  │
│  • Idempotency & Deduplication Engine (Port 8002)      │
│  • Transient /status Endpoint for Mobile Polling       │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│             FALLALERT ANDROID APPLICATION              │
│  • Real-time Sensor Streamer & Status Polling Service  │
│  • Audio Alarm & Vibration (8-second cancel window)   │
│  • Emergency SMS with Live GPS Location (Twilio/GSM)   │
│  • Automated Emergency Phone Call Dispatch             │
└────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```text
.
├── FallAlert/                               # Android Mobile Client
│   ├── app/                                 # Jetpack Compose UI, ViewModel, Background Service
│   │   ├── src/main/java/com/fallalert/app/
│   │   │   ├── alert/                       # Audio alarm, vibration, SMS & call dispatchers
│   │   │   ├── sensor/                      # IMU sensor collector, HTTP networking & location
│   │   │   ├── data/                        # Persistent contact storage
│   │   │   └── ui/                          # Modern Jetpack Compose UI screens
│   │   └── build.gradle.kts
│   └── gradle/                              # Gradle build system wrapper
│
└── Hybrid-Multimodel-Fall-Detection-System/ # AI Detection & Alert Backend
    ├── app/                                 # Streamlit 3D Digital Twin & Visualization
    ├── models/                              # Trained CNN, LSTM, GRU & YOLO models
    ├── src/
    │   ├── alerting/                        # Centralized Alert Manager (Port 8002)
    │   ├── vision/                          # YOLO11n-Pose + GRU indoor detector
    │   ├── imu/                             # Model training and data preparation
    │   └── fusion/                          # Decision fusion logic
    ├── sensor_service.py                    # Outdoor phone sensor LSTM service (Port 8000)
    └── requirements.txt                     # Python dependencies
```

---

## 🚀 Getting Started

### 1. Backend Setup & Detection Services

#### Prerequisites
- Python 3.10+
- Webcam (for indoor detection)
- Virtual environment recommended:

```bash
cd Hybrid-Multimodel-Fall-Detection-System
python -m venv .venv
.\.venv\Scripts\activate   # On Windows
pip install -r requirements.txt
```

#### Run Centralized Alert Manager
```bash
python -m src.alerting.alert_manager
```
*Listens on port `8002`.*

#### Run Outdoor Sensor Receiver (IMU + LSTM)
```bash
python sensor_service.py
```
*Listens on port `8000` and reports confirmed falls to Alert Manager.*

#### Run Indoor Vision Detector (YOLO11n-Pose + GRU)
```bash
python -m src.vision.indoor_detector
```
*Captures camera stream, extracts 17 body keypoints, and reports confirmed falls to Alert Manager.*

---

### 2. Android FallAlert Setup

1. Open Android Studio (Ladybug / Iguana or newer).
2. Select **Open** and choose the `FallAlert/` directory.
3. Allow Gradle to sync.
4. Set the **Server URL** in the app settings to your computer's local IP address (e.g., `http://192.168.1.X:8002`).
5. Configure your emergency contact details and permissions (SMS, Phone Call, Location).
6. Build and run on a physical Android device or emulator.

---

## 🛡 Features

- **Multimodal AI Detection**: Vision-based 17-point pose estimation and smartphone 9-channel inertial tracking.
- **Fail-Safe Kinematics**: Physics-based acceleration drop & collision spike filters alongside LSTM confidence scoring.
- **Deduplication & Cooldown**: Smart Alert Manager ensures no redundant alarms or false triggers.
- **Automatic Multi-channel Response**:
  - Audible loud alarm with cancel timer.
  - Automatic SMS with real-time Google Maps coordinate link.
  - Direct cellular emergency phone call.
