"""
Shared alerting layer for the hybrid fall detection system.

Holds the one centralized Alert Manager that both the indoor (webcam) and the
outdoor (smartphone sensor) detection modules report their confirmed fall
events to. The Android application keeps its own alarm + SMS + call
implementation and simply polls this service.
"""
