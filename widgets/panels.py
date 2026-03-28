from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.widgets import Label, Select, Input, RichLog, ListItem, ListView, Button, ProgressBar

from presets import PRESETS

class PresetListPanel(Vertical):
    def on_mount(self):
        self.border_title = "Recording Presets"

    def compose(self) -> ComposeResult:
        yield ListView(
            *[ListItem(Label(p.name), id=f"preset_{i}") for i, p in enumerate(PRESETS)],
            id="preset-list"
        )
        yield Label("", id="preset-desc")

class SettingsPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Label("Encoder:")
        yield Select([], id="encoder-select")
        yield Label("FPS:")
        yield Input("60", id="fps-input", type="integer")
        yield Label("Output Directory:")
        yield Input("", id="output-dir-input")

class AudioPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Label("Audio Mode:")
        yield Select([
            ("No Audio", "no_audio"),
            ("Desktop Only", "desktop"),
            ("Microphone Only", "mic"),
            ("Desktop + Microphone (Loopback)", "desktop+mic")
        ], id="audio-mode-select")
        yield Label("Desktop Monitor (Sink):")
        yield Horizontal(
            Select([], id="desktop-monitor-select"),
            Button("Mute/Unmute", id="toggle-mute-desk", variant="warning"),
            classes="device-row"
        )
        yield Label("Microphone Source:")
        yield Horizontal(
            Select([], id="mic-source-select"),
            Button("Mute/Unmute", id="toggle-mute-mic", variant="warning"),
            classes="device-row"
        )
        yield Label("Live Mic Level:")
        yield ProgressBar(total=100, show_eta=False, id="mic-meter")
        yield Horizontal(
            Button("Test Mic (3s)", id="test-audio", variant="primary"),
            Button("Monitoring: OFF", id="toggle-monitor", variant="error"),
            id="audio-buttons"
        )

class StatusPanel(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Status: Idle", id="status-label")
        yield RichLog(id="log-view", highlight=True, wrap=True)
