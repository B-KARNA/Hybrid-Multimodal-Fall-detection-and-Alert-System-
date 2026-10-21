"""
Detection services that run in the cloud container.

    outdoor_service  - phone IMU stream -> LSTM -> confirmed fall report

The indoor camera detector is NOT here: it needs a physical webcam, so it
lives in ``edge/`` and runs on the machine that has the camera.
"""
