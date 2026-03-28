import asyncio
import asyncio.subprocess
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from logging_utils import log
from presets import RecordingPreset

class Recorder:
    def __init__(self):
        self.recording_process: Optional[asyncio.subprocess.Process] = None
        self.loopback_id: Optional[str] = None
        
        self.record_null_sink_id: Optional[str] = None
        self.record_loopback_desk_id: Optional[str] = None
        self.record_loopback_mic_id: Optional[str] = None
        
        self.is_recording = False
        self.start_time: Optional[datetime] = None
        self.temp_file: Optional[Path] = None
        self.final_file: Optional[Path] = None

    async def run_cmd(self, *args, capture=True) -> Tuple[int, str, str]:
        log(f"Running: {' '.join(args)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
        except Exception as e:
            log(f"Command execution mapping error: {e}")
            return -1, "", str(e)

    async def load_pa_module(self, module_name: str, *args) -> Optional[str]:
        log(f"Loading PA module: {module_name} {' '.join(args)}")
        code, out, err = await self.run_cmd(
            "pactl", "load-module", module_name, *args
        )
        if code == 0:
            return out
        else:
            log(f"Failed to load PA module {module_name}: {err}")
            return None

    async def unload_pa_module(self, module_id: str):
        if not module_id: return
        log(f"Unloading PA module ID: {module_id}")
        await self.run_cmd("pactl", "unload-module", module_id)

    async def start(
        self,
        preset: RecordingPreset,
        encoder: str,
        fps: int,
        audio_mode: str,
        desktop_monitor: Optional[str],
        mic_source: Optional[str],
        desktop_sink: Optional[str],
        output_dir: str
    ):
        if self.is_recording:
            log("Already recording!")
            return False

        self.start_time = datetime.now()
        timestamp = self.start_time.strftime("%Y-%m-%d_%H%M%S")
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        temp_file = out_dir / f"temp_wfr_tui_{timestamp}.mp4"
        self.final_file = out_dir / f"wfr_{timestamp}.mp4"
        self.temp_file = temp_file

        cmd = ["wf-recorder", "-f", str(temp_file)]
        cmd.extend(["-r", str(fps)])

        # Hardware encode handling - assumes caller passed exact encoder string
        if "vaapi" in encoder:
             cmd.extend(["-c", encoder, "-d", "/dev/dri/renderD128", "-D"])
        else:
             cmd.extend(["-c", encoder])

        # Audio handling
        self.loopback_id = None
        audio_arg = None
        cmd_args = cmd.copy()
        
        if audio_mode == "desktop+mic":
            if mic_source and desktop_sink and desktop_monitor:
                self.record_null_sink_id = await self.load_pa_module("module-null-sink", "sink_name=wfr_record_sink", "sink_properties=device.description=WfrTuiMixer")
                if self.record_null_sink_id:
                    self.record_loopback_desk_id = await self.load_pa_module("module-loopback", f"source={desktop_monitor}", "sink=wfr_record_sink", "latency_msec=5")
                    self.record_loopback_mic_id = await self.load_pa_module("module-loopback", f"source={mic_source}", "sink=wfr_record_sink", "latency_msec=5")
                    audio_arg = "wfr_record_sink.monitor"
                else:
                    self.loopback_id = await self.load_pa_module("module-loopback", f"source={mic_source}", f"sink={desktop_sink}")
                    audio_arg = desktop_monitor
            else:
                log("Missing mic/sink for loopback. Audio disabled.")
        elif audio_mode == "desktop":
            if desktop_monitor:
                audio_arg = desktop_monitor
        elif audio_mode == "mic":
            if mic_source:
                audio_arg = mic_source

        if audio_arg:
            cmd_args.append(f"--audio={audio_arg}")
            # Beri jeda 0.5 detik agar PulseAudio/PipeWire selesai menginisialisasi null-sink .monitor
            await asyncio.sleep(0.5)
        else:
            if audio_mode != "no_audio":
                log("Audio requested but device missing. Recording without audio.")
                
        log(f"Starting wf-recorder: {' '.join(cmd_args)}")
        try:
            self.recording_process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            self.is_recording = True
            log("Recording started.")
            # Start background task to consume output so it doesn't block
            asyncio.create_task(self._consume_output())
            return True
        except Exception as e:
            log(f"Failed to start wf-recorder: {e}")
            self.cleanup()
            return False

    async def _consume_output(self):
        proc = self.recording_process
        if proc is None:
            return
        stdout = proc.stdout
        if stdout is None:
            return
        while True:
            line = await stdout.readline()
            if not line:
                break
            # Can conditionally log here, but we'll ignore it to avoid flooding
            pass
            
        await proc.wait()
        log(f"wf-recorder exited with code {proc.returncode}")
        
        if self.is_recording:
             # means it wasn't stopped manually via stop()
             self.is_recording = False
             await self.post_process()

    async def stop(self):
        proc = self.recording_process
        if not self.is_recording or proc is None:
            return

        log("Stopping recording...")
        self.is_recording = False
        proc.send_signal(signal.SIGINT)
        
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            log("Process didn't stop gracefully, terminating...")
            proc.terminate()
            await proc.wait()

        await self.post_process()

    async def post_process(self):
        desk_id = self.record_loopback_desk_id
        if desk_id:
            await self.unload_pa_module(desk_id)
            self.record_loopback_desk_id = None
            
        mic_id = self.record_loopback_mic_id
        if mic_id:
            await self.unload_pa_module(mic_id)
            self.record_loopback_mic_id = None
            
        null_id = self.record_null_sink_id
        if null_id:
            await self.unload_pa_module(null_id)
            self.record_null_sink_id = None            
            
        loop_id = self.loopback_id
        if loop_id:
            await self.unload_pa_module(loop_id)
            self.loopback_id = None

        temp = self.temp_file
        if temp and temp.exists():
            log("Starting ffmpeg post-processing...")
            cmd = [
                "ffmpeg", "-y", "-i", str(temp),
                "-video_track_timescale", "60k",
                "-c", "copy", str(self.final_file)
            ]
            code, out, err = await self.run_cmd(*cmd, capture=True)
            if code == 0:
                log(f"Post-processing complete. File saved to: {self.final_file}")
                try:
                    if temp: temp.unlink()
                except Exception as e:
                    log(f"Failed to delete temp file: {e}")
            else:
                log(f"ffmpeg post-processing failed! Code: {code}")
                # Keep temp file if ffmpeg fails

    def cleanup(self):
        self.is_recording = False
        desk_id = self.record_loopback_desk_id
        if desk_id:
             asyncio.create_task(self.unload_pa_module(desk_id))
             self.record_loopback_desk_id = None
             
        mic_id = self.record_loopback_mic_id
        if mic_id:
             asyncio.create_task(self.unload_pa_module(mic_id))
             self.record_loopback_mic_id = None
             
        null_id = self.record_null_sink_id
        if null_id:
             asyncio.create_task(self.unload_pa_module(null_id))
             self.record_null_sink_id = None             
             
        loop_id = self.loopback_id
        if loop_id:
            asyncio.create_task(self.unload_pa_module(loop_id))
            self.loopback_id = None
