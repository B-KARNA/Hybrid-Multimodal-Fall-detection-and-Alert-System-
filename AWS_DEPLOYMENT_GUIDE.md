# AWS Deployment & Containerization Guide
## Hybrid Multimodal Fall Detection and Alert System (HMFDA)

This guide provides end-to-end instructions for **containerizing** the HMFDA project with Docker and **deploying** it to **Amazon Web Services (AWS)**. It covers both the backend AI services and the **FallAlert Android mobile application (`.apk`)**.

---

## 🏛 Deployment Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        ANDROID MOBILE CLIENT                           │
│  • FallAlert App (.apk installed on smartphone)                        │
│  • 9-Channel IMU Sensor Stream (Acc/Gyro/Gravity)                      │
│  • Audio Siren + 8s Cancel Countdown + Auto SMS with GPS + Auto Call   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ HTTP POST sensor data & GET /status
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        AWS EC2 CLUSTER (DOCKER)                        │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     NGINX GATEWAY (Port 80)                      │  │
│  │  • Web Portal & 1-Click APK Download (/download/fallalert.apk)   │  │
│  │  • Reverse Proxy for Microservices & Streamlit WebSockets        │  │
│  └───────┬──────────────────────────┬────────────────────────┬──────┘  │
│          │                          │                        │         │
│          ▼                          ▼                        ▼         │
│  ┌───────────────┐          ┌───────────────┐        ┌──────────────┐  │
│  │ ALERT MANAGER │◄─────────┤ SENSOR ENGINE │        │ 3D DASHBOARD │  │
│  │  (Port 8002)  │          │  (Port 8000)  │        │ (Port 8501)  │  │
│  │  Deduplication│          │  Keras LSTM   │        │ Streamlit 3D │  │
│  │  Hold Window  │          │  Kinematics   │        │ Caretakers   │  │
│  │  Status Poller│          │  Inference    │        │ History Log  │  │
│  └───────▲───────┘          └───────────────┘        └──────────────┘  │
└──────────┼─────────────────────────────────────────────────────────────┘
           │ Confirmed Vision Falls (POST /event)
┌──────────┴─────────────────────────────────────────────────────────────┐
│                   INDOOR VISION DETECTOR (EDGE / PC)                   │
│  • Live Room Camera Feed + YOLO11n-Pose (17 Keypoints) + GRU           │
│  • Reports confirmed falls to http://<AWS-IP>:8002/event               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Containerization Overview

The system is split into modular microservices orchestrated with **Docker Compose**:

| Container | Service Name | Internal Port | Host Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `hmfda-gateway` | `gateway` | `80` | `80` | Nginx reverse proxy & static APK download server |
| `hmfda-alert-manager` | `alert-manager` | `8002` | `8002` | Centralized alert manager & mobile polling endpoint |
| `hmfda-sensor-service` | `sensor-service` | `8000` | `8000` | Outdoor smartphone IMU LSTM neural classifier |
| `hmfda-dashboard` | `dashboard` | `8501` | `8501` | Streamlit 3D Digital Twin & Caretaker management |

---

## 🛠 Local Testing with Docker

Before deploying to AWS, test the containerized stack locally on your computer:

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### 2. Launch Stack
Open your terminal in `d:\HMFDA`:

```bash
# Build and start all services in the background
docker compose up -d --build
```

### 3. Verify
- Open your browser to: `http://localhost`
- You will see the **HMFDA Cloud Gateway** landing page with the **Download APK** button!
- Open the 3D Dashboard: `http://localhost/dashboard/` (or `http://localhost:8501`)
- Verify Alert Manager: `http://localhost:8002/status`

To stop the containers:
```bash
docker compose down
```

---

## ☁️ Step-by-Step AWS Cloud Deployment

### Step 1: Launch an AWS EC2 Instance

1. Log into your [AWS Management Console](https://aws.amazon.com/console/).
2. Navigate to **EC2** -> **Instances** -> Click **Launch Instance**.
3. Configure the instance:
   - **Name**: `HMFDA-FallDetection-Server`
   - **OS Image**: **Ubuntu Server 24.04 LTS** (or 22.04 LTS), 64-bit (x86_64).
   - **Instance Type**:
     - **Recommended**: `t3.medium` (2 vCPU, 4 GiB RAM) or `t3.large` (2 vCPU, 8 GiB RAM).
     - *Note: `t3.micro` is not recommended due to memory requirements during TensorFlow Docker builds.*
   - **Key Pair**: Select an existing key pair or click **Create new key pair** (e.g. `hmfda-key.pem`) and download it.
   - **Storage**: Set to at least **30 GiB gp3 SSD** to accommodate Docker images and models.

---

### Step 2: Configure EC2 Security Group (Firewall)

Under **Network Settings**, configure the following **Inbound Security Group Rules**:

| Type | Port Range | Protocol | Source | Description |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | `22` | TCP | Your IP (or `0.0.0.0/0`) | Remote SSH terminal access |
| **HTTP** | `80` | TCP | `0.0.0.0/0` | Web Gateway & APK download portal |
| **HTTPS** | `443` | TCP | `0.0.0.0/0` | Secure SSL Web access (optional) |
| **Custom TCP** | `8002` | TCP | `0.0.0.0/0` | Central Alert Manager (FallAlert app) |
| **Custom TCP** | `8000` | TCP | `0.0.0.0/0` | Outdoor Sensor Service (Direct stream) |
| **Custom TCP** | `8501` | TCP | `0.0.0.0/0` | Streamlit 3D Digital Twin Dashboard |

Click **Launch Instance**.

---

### Step 3: Connect to your EC2 Instance

Once the instance shows **Running**, copy its **Public IPv4 Address** (e.g., `3.85.120.45`).

Open your terminal and SSH into the instance:
```bash
chmod 400 hmfda-key.pem
ssh -i hmfda-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

---

### Step 4: Transfer Code and Deploy

You have two easy ways to get your code onto the EC2 instance:

#### Option A: Clone from GitHub (Fastest)
If your repository is on GitHub:
```bash
git clone https://github.com/B-KARNA/Hybrid-Multimodal-Fall-detection-and-Alert-System-.git HMFDA
cd HMFDA
chmod +x deploy-aws.sh
./deploy-aws.sh
```

#### Option B: Upload from Local Machine via SCP
From your local Windows command line:
```powershell
# Copy the project to EC2
scp -i hmfda-key.pem -r d:\HMFDA ubuntu@<YOUR-EC2-PUBLIC-IP>:~/HMFDA
```
Then on the EC2 terminal:
```bash
cd ~/HMFDA
chmod +x deploy-aws.sh
./deploy-aws.sh
```

The `deploy-aws.sh` script automatically:
1. Installs Docker and Docker Compose Plugin.
2. Allocates a 2GB Swap file for smooth compilation.
3. Builds the Docker images.
4. Starts the containers with healthchecks.
5. Prints all active URLs and mobile setup instructions.

---

### Step 5: Android Mobile App (`FallAlert`) Setup

Now your backend is live in the cloud! Connect the smartphone app:

1. **Install the APK on Phone**:
   - Open your mobile browser on your Android phone.
   - Navigate to: `http://<YOUR-EC2-PUBLIC-IP>/download/fallalert.apk`
   - Download and install `FallAlert.apk` (allow "Install unknown apps" if prompted).

2. **Configure App Settings**:
   - Open the **FallAlert** app.
   - Tap **Settings** (or the Server URL config).
   - Enter your AWS Public IP:
     ```text
     http://<YOUR-EC2-PUBLIC-IP>:8002
     ```
   - Add your emergency contact phone number.
   - Grant required permissions: **SMS**, **Phone Calls**, **Physical Activity / Sensors**, **Location (GPS)**.

3. **Start Fall Protection**:
   - Tap **START TRACKING**.
   - The app now continuously streams sensor kinematics to your AWS cloud LSTM model!

---

### Step 6: Connect Indoor Vision Detector (Webcam on Edge PC)

Because AWS EC2 instances do not have physical webcams attached, run the vision detector on any indoor PC, laptop, or Raspberry Pi with a camera:

1. Open `Hybrid-Multimodel-Fall-Detection-System/src/vision/indoor_detector.py` or set the environment variable:
   ```bash
   export ALERT_MANAGER_URL="http://<YOUR-EC2-PUBLIC-IP>:8002"
   ```
2. Start the vision detector:
   ```bash
   python -m src.vision.indoor_detector
   ```
3. Whenever a fall is detected in the room camera feed, it posts to the AWS Alert Manager, which immediately sends the alarm to the Android mobile app!

---

## 🔧 Useful Operational Commands on AWS

| Task | Command |
| :--- | :--- |
| **Check container status** | `sudo docker compose ps` |
| **View live logs** | `sudo docker compose logs -f` |
| **View Alert Manager logs** | `sudo docker compose logs -f alert-manager` |
| **View Sensor LSTM logs** | `sudo docker compose logs -f sensor-service` |
| **Restart services** | `sudo docker compose restart` |
| **Stop all services** | `sudo docker compose down` |
| **Update & Rebuild after git pull** | `git pull && sudo docker compose up -d --build` |

---

## 🔒 Optional: Add Free SSL / HTTPS with Let's Encrypt

If you map a custom domain (e.g. `fallalert.yourdomain.com`) to your EC2 IP:

1. Install Certbot on EC2:
   ```bash
   sudo apt-get install -y certbot python3-certbot-nginx
   ```
2. Run Certbot to automatically configure SSL:
   ```bash
   sudo certbot --nginx -d fallalert.yourdomain.com
   ```
3. Both web traffic and mobile API traffic will now be secured with HTTPS!
