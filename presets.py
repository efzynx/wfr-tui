from dataclasses import dataclass

@dataclass
class RecordingPreset:
    name: str
    description: str
    fps: int
    target_usage: str  # "youtube", "editing", "low_resource", "custom"
    prefer_hardware: bool  # True = prefer VAAPI
    force_software: bool   # True = always use libx264
    audio_mode_default: str  # "no_audio", "desktop", "mic", "desktop+mic"

PRESETS = [
    RecordingPreset(
        name="YouTube 1080p60 (Hardware)",
        description="Balanced quality for YouTube at 1080p60. Uses hardware encoder when available.",
        fps=60,
        target_usage="youtube",
        prefer_hardware=True,
        force_software=False,
        audio_mode_default="desktop+mic"
    ),
    RecordingPreset(
        name="YouTube 1080p60 (Software)",
        description="Balanced quality for YouTube at 1080p60. Consistent x264 software encoding.",
        fps=60,
        target_usage="youtube",
        prefer_hardware=False,
        force_software=True,
        audio_mode_default="desktop+mic"
    ),
    RecordingPreset(
        name="Editing (High quality)",
        description="High quality for editing, even with larger file sizes.",
        fps=60,
        target_usage="editing",
        prefer_hardware=False,
        force_software=False,
        audio_mode_default="desktop+mic"
    ),
    RecordingPreset(
        name="Low Resource (720p30)",
        description="Lower load on CPU/GPU. Suitable for older machines.",
        fps=30,
        target_usage="low_resource",
        prefer_hardware=True,
        force_software=False,
        audio_mode_default="desktop"
    ),
    RecordingPreset(
        name="Custom",
        description="User can adjust all fields manually.",
        fps=60,
        target_usage="custom",
        prefer_hardware=False,
        force_software=False,
        audio_mode_default="no_audio"
    )
]
