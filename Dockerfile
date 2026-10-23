# ============================================================
# Dockerfile - Hybrid Multimodal Fall Detection & Alert System (HMFDA)
# Full Stack: Streamlit 3D Digital Twin, YOLO11-Pose, GRU & LSTM
# ============================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system libraries needed by OpenCV, Streamlit, and ffmpeg for H.264 video rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY docker/requirements-dashboard.txt /tmp/requirements-dashboard.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements-dashboard.txt

# Copy backend application source code, models, and dashboard
COPY Hybrid-Multimodel-Fall-Detection-System/ /app/

# Expose ports: Streamlit Dashboard (8501), Sensor Service (8000), Alert Manager (8002)
EXPOSE 8501 8000 8002

# Healthcheck to verify Streamlit service is healthy
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit monitoring dashboard
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
