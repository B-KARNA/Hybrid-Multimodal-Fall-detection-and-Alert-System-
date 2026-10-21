"""
FallAlert deployable backend package.

This package holds everything that runs in the cloud container:

    fallalert.paths      - one filesystem resolver for every module
    fallalert.config     - ports, URLs and thresholds (single source of truth)
    fallalert.alerting   - the centralized Alert Manager
    fallalert.detectors  - the outdoor IMU/LSTM service

It deliberately does NOT import tensorflow, torch, ultralytics, opencv or
streamlit at package level, so importing it stays cheap and the container
image stays small. Hardware-bound code lives in ``edge/`` and the dashboard
lives in ``dashboard/``.
"""
