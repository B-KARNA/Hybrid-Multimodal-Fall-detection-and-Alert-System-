# Dashboard image: the Streamlit UI.
#
# This is a SEPARATE service from the backend. It needs torch, ultralytics and
# streamlit - the exact packages the backend image deliberately omits - so it
# must never be merged into the backend container.
#
# Build from the repository root:
#     docker build -f deploy/dashboard.Dockerfile -t fallalert-dashboard .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

# libgl1 / libglib2.0-0 are required to import cv2 even in the headless build;
# ffmpeg backs the streamlit-webrtc video decoding.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/dashboard.txt /app/requirements/dashboard.txt

RUN pip install --no-cache-dir -r /app/requirements/dashboard.txt

# The dashboard resolves models from PROJECT_ROOT (/app), so all model
# families are copied here - unlike the backend image.
COPY models/ /app/models/
COPY dashboard/ /app/dashboard/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
