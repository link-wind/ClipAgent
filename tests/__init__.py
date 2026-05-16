import os
from pathlib import Path


os.environ.setdefault("CLIPFORGE_PLANNER_MODE", "deterministic")
os.environ.setdefault(
    "CLIPFORGE_RUNTIME_CONFIG_PATH",
    str(Path(__file__).resolve().parents[1] / ".tmp" / "runtime_config.unittest.json"),
)
