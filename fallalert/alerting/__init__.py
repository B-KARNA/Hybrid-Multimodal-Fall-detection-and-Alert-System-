"""
Centralized alerting layer.

Contains the one Alert Manager that both detection modules report their
confirmed fall events to. The Android app keeps its own alarm + SMS + call
implementation and simply polls this service.
"""
