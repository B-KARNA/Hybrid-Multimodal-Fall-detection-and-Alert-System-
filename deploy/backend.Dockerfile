# Backend image: centralized Alert Manager + outdoor detector.
#
# Deliberately narrow. Only numpy + tensorflow-cpu are installed and only the
# outdoor model folder is copied, so torch, ultralytics, streamlit and opencv
# are never present. That keeps the image small and the build fast.
#
# Build from the repository root:
#     docker build -f deploy/backend.Dockerfile -t fallalert-backend .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    FALLALERT_ROOT=/app \
    ALERT_MANAGER_HOST=0.0.0.0 \
    ALERT_MANAGER_PORT=8002 \
    OUTDOOR_DETECTOR_HOST=0.0.0.0 \
    OUTDOOR_DETECTOR_PORT=8000 \
    OUTDOOR_DETECTOR_URL=http://127.0.0.1:8000

WORKDIR /app

# libgomp1 provides the OpenMP runtime TensorFlow links against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/backend.txt /app/requirements/backend.txt

RUN pip install --no-cache-dir -r /app/requirements/backend.txt

# Only the outdoor artefacts are needed - vision/ and imu/ stay out of the image.
COPY models/outdoor/ /app/models/outdoor/
COPY fallalert/ /app/fallalert/

EXPOSE 8002
EXPOSE 8000

# The outdoor detector must be listening before the Alert Manager can relay to
# it, so it is started first. The Manager degrades gracefully (it answers
# connected:false) while port 8000 is still coming up from a slow TF model
# load, so startup order cannot crash the service.
CMD ["sh", "-c", "python -m fallalert.detectors.outdoor_service & exec python -m fallalert.alerting.alert_manager"]
