import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "wfr-tui"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Videos"


@dataclass
class AppConfig:
    last_preset_name: str = "YouTube 1080p60 (Hardware)"
    custom_fps: int = 60
    custom_encoder: str = "libx264"
    custom_audio_mode: str = "desktop+mic"
    output_dir: str = str(DEFAULT_OUTPUT_DIR)

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception:
                pass
        return cls()

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=4)
