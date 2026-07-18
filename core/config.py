from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
RESOURCES_DIR: Path = PROJECT_ROOT / "resources"


def user_data_dir(app_name: str) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / app_name


@dataclass(frozen=True)
class Config:
    app_name: str = "Lockpekku"
    accent_hex: str = "#ffb000"
    default_root: str = "N:\\"
    live_interval_ms: int = 2500
    window_width: int = 1160
    window_height: int = 640
