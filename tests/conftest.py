"""The pure core can be tested without importing Home Assistant's adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components/radiant_climate"))
