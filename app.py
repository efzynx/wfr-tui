import asyncio
import struct
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Label, Select, Input, RichLog, ListView, ListItem, Button, Header, Footer, Collapsible

from config import AppConfig
from detection import detect_hardware, detect_audio, HardwareCapabilities, AudioCapabilities
from logging_utils import app_logger, log
from presets import PRESETS, RecordingPreset
from recorder import Recorder
from widgets.panels import PresetListPanel, SettingsPanel, AudioPanel, StatusPanel

class WfrTuiApp(App):
    CSS_PATH = "wfr_tui.tcss"
    TITLE = "wfr-tui (wf-recorder TUI)"

    BINDINGS = [
        Binding("space", "toggle_record", "Start/Stop"),
        Binding("q", "request_quit", "Quit"),
        Binding("f1", "show_help", "Help"),
        Binding("tab", "focus_next", "Navigate", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = AppConfig.load()
        self.hardware: Optional[HardwareCapabilities] = None
        self.audio: Optional[AudioCapabilities] = None
        self.recorder = Recorder()
        self.current_preset = PRESETS[0]
        self.monitoring_loopback_id: Optional[str] = None
        self.meter_proc = None
        self.meter_task = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield PresetListPanel(id="presets-panel", classes="panel")
            with Container(id="right-panels"):
                with Collapsible(title="Recording Settings", collapsed=True, id="col-settings", classes="accordion-item"):
                    yield SettingsPanel(id="settings-panel")
                with Collapsible(title="Audio Settings", collapsed=True, id="col-audio", classes="accordion-item"):
                    yield AudioPanel(id="audio-panel")
                with Collapsible(title="Status & Logs", collapsed=False, id="col-status", classes="accordion-item"):
                    yield StatusPanel(id="status-panel")
        yield Footer()

    async def on_mount(self):
        log("wfr-tui initializing...")
        app_logger.subscribe(self.handle_log_message)

        # Detect caps
        self.hardware = detect_hardware()
        self.audio = detect_audio()

        if not self.hardware.has_wf_recorder:
            log("ERROR: wf-recorder not found. You must install wf-recorder.")
        if not self.hardware.has_pactl:
            log("WARNING: pactl not found. Loopback and audio detection may fail.")
        if not self.hardware.has_ffmpeg:
            log("WARNING: ffmpeg not found. Post-processing will be disabled.")
        if self.hardware.has_vaapi:
            log(f"Detected VAAPI device: {self.hardware.vaapi_device}. Encoders: {', '.join(self.hardware.vaapi_encoders)}")
        else:
            log("No VAAPI found. Software encoding only.")

        self.populate_dropdowns()
        self.apply_preset(PRESETS[0])
        
        # Mulai meter audio pertama kali
        mic_source = self.query_one("#mic-source-select", Select).value
        if mic_source:
             asyncio.create_task(self.start_mic_meter(mic_source))
        
        # Try to restore last selected preset
        preset_idx = 0
        for i, p in enumerate(PRESETS):
            if p.name == self.config.last_preset_name:
                preset_idx = i
                break
        
        list_view = self.query_one("#preset-list", ListView)
        if list_view.children:
            list_view.index = preset_idx
            
    def handle_log_message(self, message: str):
        # Must be careful with threads, but our logger is synchronous in the asyncio loop
        try:
            log_view = self.query_one("#log-view", RichLog)
            log_view.write(message)
        except Exception:
            pass

    def populate_dropdowns(self):
        # Encoder
        encoder_options = []
        if self.hardware and self.hardware.has_vaapi:
            for enc in self.hardware.vaapi_encoders:
                encoder_options.append((f"Hardware: {enc}", enc))
        encoder_options.append(("Software: libx264", "libx264"))
        
        enc_select = self.query_one("#encoder-select", Select)
        enc_select.set_options(encoder_options)
        
        # Audio
        if self.audio:
            desk_opts = [(s, s) for s in self.audio.monitor_sources]
            desk_select = self.query_one("#desktop-monitor-select", Select)
            desk_select.set_options(desk_opts)
            if self.audio.default_sink_monitor and desk_opts:
                desk_select.value = self.audio.default_sink_monitor
            elif desk_opts:
                desk_select.value = desk_opts[0][1]

            mic_opts = [(s, s) for s in self.audio.mic_sources]
            mic_select = self.query_one("#mic-source-select", Select)
            mic_select.set_options(mic_opts)
            if self.audio.default_source and mic_opts:
                 for mm in mic_opts:
                     if self.audio.default_source in mm[1]:
                         mic_select.value = mm[1]
                         break
                 else:
                     mic_select.value = mic_opts[0][1]
            elif mic_opts:
                mic_select.value = mic_opts[0][1]

        # Output Dir
        self.query_one("#output-dir-input", Input).value = self.config.output_dir

    def apply_preset(self, preset: RecordingPreset):
        self.current_preset = preset
        self.query_one("#preset-desc", Label).update(preset.description)
        self.query_one("#fps-input", Input).value = str(preset.fps)

        enc_select = self.query_one("#encoder-select", Select)
        if preset.target_usage == "custom":
            enc_select.value = self.config.custom_encoder
            self.query_one("#audio-mode-select", Select).value = self.config.custom_audio_mode
        else:
            if preset.prefer_hardware and self.hardware and self.hardware.has_vaapi and not preset.force_software:
                 # Pick first hardware encoder (prefer h264_vaapi if available)
                 best_enc = self.hardware.vaapi_encoders[0]
                 for enc in self.hardware.vaapi_encoders:
                     if "h264" in enc:
                         best_enc = enc
                         break
                 enc_select.value = best_enc
            else:
                 enc_select.value = "libx264"
             
            self.query_one("#audio-mode-select", Select).value = preset.audio_mode_default

    def on_list_view_selected(self, event: ListView.Selected):
        item_id = event.item.id
        if item_id and item_id.startswith("preset_"):
            idx = int(item_id.split("_")[1])
            self.apply_preset(PRESETS[idx])

    def on_collapsible_expanded(self, event: Collapsible.Expanded):
        # Mode Accordion: Hanya 1 panel yang terbuka
        for col in self.query(Collapsible):
            if col != event.collapsible:
                col.collapsed = True

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "mic-source-select" and event.value:
            asyncio.create_task(self.start_mic_meter(event.value))

    async def action_toggle_record(self):
        if not self.hardware.has_wf_recorder:
            log("Cannot record: wf-recorder is missing.")
            return

        status_label = self.query_one("#status-label", Label)
        if self.recorder.is_recording:
             # Stop
             await self.recorder.stop()
             status_label.update("Status: Idle")
             
             # Save config
             self._save_config()
        else:
             # Start
             encoder = self.query_one("#encoder-select", Select).value
             fps_str = self.query_one("#fps-input", Input).value
             try:
                 fps = int(fps_str)
             except ValueError:
                 fps = 60
                 
             audio_mode = self.query_one("#audio-mode-select", Select).value
             desktop_monitor = self.query_one("#desktop-monitor-select", Select).value
             mic_source = self.query_one("#mic-source-select", Select).value
             out_dir = self.query_one("#output-dir-input", Input).value
             
             if not encoder or not out_dir:
                 log("Missing settings. Check encoder and output directory.")
                 return

             success = await self.recorder.start(
                 self.current_preset,
                 encoder,
                 fps,
                 audio_mode,
                 desktop_monitor,
                 mic_source,
                 desktop_sink="alsa_output.pci-0000_00_1f.3.analog-stereo" if not self.audio.default_sink else self.audio.default_sink,
                 output_dir=out_dir
             )
             
             if success:
                 status_label.update("Status: Recording...")

    async def action_request_quit(self):
        if self.recorder.is_recording:
            # Optionally show a confirmation dialog
            log("Stopping recording before quit...")
            await self.recorder.stop()
        
        self._save_config()
        self.exit()

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "test-audio":
            await self.action_test_audio()
        elif event.button.id == "toggle-monitor":
            await self.action_toggle_monitor()
        elif event.button.id == "toggle-mute-desk":
            await self.action_toggle_mute("sink", self.query_one("#desktop-monitor-select", Select).value)
        elif event.button.id == "toggle-mute-mic":
            await self.action_toggle_mute("source", self.query_one("#mic-source-select", Select).value)

    async def action_toggle_mute(self, device_type: str, device_name: str):
        if not device_name:
            return
            
        if device_type == "sink" and device_name.endswith(".monitor"):
            device_name = device_name.replace(".monitor", "")

        try:
            proc = await asyncio.create_subprocess_exec(
                "pactl", f"set-{device_type}-mute", device_name, "toggle"
            )
            await proc.wait()
            log(f"Toggle mute state for {device_type} '{device_name}'")
        except Exception as e:
            log(f"Failed to toggle mute: {e}")

    async def start_mic_meter(self, mic_source: str):
        from textual.widgets import ProgressBar
        if self.meter_proc:
            try:
                self.meter_proc.terminate()
            except Exception:
                pass
        if self.meter_task:
            self.meter_task.cancel()

        cmd = ["parec", "-d", mic_source, "--raw", "--format=s16le", "--channels=1", "--rate=8000"]
        try:
            self.meter_proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            self.meter_task = asyncio.create_task(self._meter_loop())
        except Exception as e:
            log(f"Failed to start audio meter: {e}")

    async def _meter_loop(self):
        from textual.widgets import ProgressBar
        meter = self.query_one("#mic-meter", ProgressBar)
        while True:
            try:
                data = await self.meter_proc.stdout.read(800)
                if not data:
                    break
                
                num_samples = len(data) // 2
                if num_samples == 0:
                    continue
                fmt = f"<{num_samples}h"
                samples = struct.unpack(fmt, data)
                
                peak = max(abs(s) for s in samples)
                percent = (peak / 32768.0) * 100
                meter.progress = percent
            except Exception:
                break
                
    async def action_test_audio(self):
        mic_source = self.query_one("#mic-source-select", Select).value
        if not mic_source:
            log("Pilih microphone terlebih dahulu.")
            return
            
        status_label = self.query_one("#status-label", Label)
        status_label.update("Status: Sedang merekam (3 detik)...")
        log("Memulai test audio 3 detik...")
        
        btn = self.query_one("#test-audio", Button)
        btn.disabled = True
        
        temp_wav = "/tmp/wfr_tui_test_mic.wav"
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "parecord", "-d", mic_source, "--process-time-msec=10", temp_wav,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.sleep(3)
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()
                
            status_label.update("Status: Memutar hasil rekaman...")
            log("Mendengarkan hasil test audio...")
            
            play_proc = await asyncio.create_subprocess_exec(
                "paplay", temp_wav
            )
            await play_proc.wait()
            log("Test audio selesai.")
        except Exception as e:
            log(f"Test audio gagal: {e}")
            
        status_label.update("Status: Idle")
        btn.disabled = False
        
    async def action_toggle_monitor(self):
        btn = self.query_one("#toggle-monitor", Button)
        if self.monitoring_loopback_id:
            await self.recorder.unload_pa_module(self.monitoring_loopback_id)
            self.monitoring_loopback_id = None
            btn.label = "Monitoring: OFF"
            btn.variant = "error"
            log("Monitoring dimatikan.")
        else:
            mic_source = self.query_one("#mic-source-select", Select).value
            desk_sink = self.audio.default_sink if self.audio and self.audio.default_sink else "alsa_output.pci-0000_00_1f.3.analog-stereo"
            
            if not mic_source:
                log("Microphone belum dipilih.")
                return
                
            self.monitoring_loopback_id = await self.recorder.load_pa_module("module-loopback", f"source={mic_source}", f"sink={desk_sink}", "latency_msec=1")
            if self.monitoring_loopback_id:
                btn.label = "Monitoring: ON"
                btn.variant = "success"
                log("Monitoring diaktifkan.")

    def _save_config(self):
        try:
             self.config.last_preset_name = self.current_preset.name
             if self.current_preset.target_usage == "custom":
                 self.config.custom_encoder = self.query_one("#encoder-select", Select).value
                 self.config.custom_fps = int(self.query_one("#fps-input", Input).value)
                 self.config.custom_audio_mode = self.query_one("#audio-mode-select", Select).value
             self.config.output_dir = self.query_one("#output-dir-input", Input).value
             self.config.save()
        except Exception as e:
             log(f"Failed to save config: {e}")

    def action_show_help(self):
        log("Usage: Space -> Start/Stop, Up/Down/Tab -> Navigate, Q -> Quit")

if __name__ == "__main__":
    app = WfrTuiApp()
    app.run()
