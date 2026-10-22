"""
Single source of truth for filesystem locations.

Every deployable module imports its paths from here instead of computing
``Path(__file__).resolve().parents[N]`` locally. That old pattern breaks
silently whenever a file is moved one level up or down - the classic
"model file not found" error after a restructure.

In the container the layout is::

    /app/
        fallalert/          <- this package
        models/outdoor/     <- COPYed model + scaler
    /app/models/outdoor/best_outdoor_lstm.keras

so ``parents[1]`` from ``/app/fallalert/paths.py`` already resolves to
``/app``. ``FALLALERT_ROOT`` is available as an override for the case where
the tree is laid out differently (for example a partial COPY).
"""

import os
from pathlib import Path


# Layout: <repo>/fallalert/paths.py  ->  the repository root is two levels up.
_DEFAULT_ROOT = Path(__file__).resolve().parents[1]


PROJECT_ROOT = Path(
    os.environ.get("FALLALERT_ROOT", str(_DEFAULT_ROOT))
).resolve()


MODELS_DIR = PROJECT_ROOT / "models"


OUTDOOR_DIR = MODELS_DIR / "outdoor"

VISION_DIR = MODELS_DIR / "vision"


# ---------------------------------------------------------
# Model artefacts
# ---------------------------------------------------------

# Outdoor IMU/LSTM (used by fallalert.detectors.outdoor_service)
OUTDOOR_MODEL = OUTDOOR_DIR / "best_outdoor_lstm.keras"

OUTDOOR_SCALER = OUTDOOR_DIR / "outdoor_lstm_scaler.npz"


# Indoor camera pipeline (used by edge/indoor_detector.py)
VISION_GRU_MODEL = VISION_DIR / "best_gru.keras"

YOLO_POSE_MODEL = VISION_DIR / "yolo11n-pose.pt"


def require(path):
    """
    Fail early with a readable message when a required artefact is missing.

    A missing model in a container is otherwise reported by Keras as a bare
    OSError with no hint about which path was tried.
    """

    if not Path(path).exists():

        raise FileNotFoundError(
            f"Required file not found: {path}\n"
            f"PROJECT_ROOT resolves to: {PROJECT_ROOT}\n"
            f"Set the FALLALERT_ROOT environment variable if the project "
            f"root is somewhere else."
        )

    return path
