import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class HardwareCapabilities:
    has_vaapi: bool = False
    vaapi_encoders: List[str] = field(default_factory=list)
    vaapi_device: Optional[str] = None
    fallback_encoder: str = "libx264"
    has_pactl: bool = False
    has_wf_recorder: bool = False
    has_ffmpeg: bool = False

@dataclass
class AudioCapabilities:
    desktop_sinks: List[str] = field(default_factory=list)
    monitor_sources: List[str] = field(default_factory=list)
    mic_sources: List[str] = field(default_factory=list)
    default_sink: Optional[str] = None
    default_source: Optional[str] = None
    default_sink_monitor: Optional[str] = None

def check_command(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def detect_hardware() -> HardwareCapabilities:
    caps = HardwareCapabilities()
    
    caps.has_wf_recorder = check_command("wf-recorder")
    caps.has_pactl = check_command("pactl")
    caps.has_ffmpeg = check_command("ffmpeg")
    
    if caps.has_ffmpeg:
        try:
            res = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
            output = res.stdout.lower()
            if "h264_vaapi" in output:
                caps.vaapi_encoders.append("h264_vaapi")
            if "hevc_vaapi" in output:
                caps.vaapi_encoders.append("hevc_vaapi")
        except Exception:
            pass
            
    if os.path.exists("/dev/dri/renderD128"):
        caps.vaapi_device = "/dev/dri/renderD128"
        
    caps.has_vaapi = len(caps.vaapi_encoders) > 0 and caps.vaapi_device is not None
    return caps

def detect_audio() -> AudioCapabilities:
    caps = AudioCapabilities()
    if not check_command("pactl"):
        return caps

    try:
        res_sinks = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True)
        res_sources = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True)
        res_def_sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True)
        res_def_src = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True)
        
        caps.default_sink = res_def_sink.stdout.strip()
        caps.default_source = res_def_src.stdout.strip()
        
        for line in res_sinks.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                sink_name = parts[1]
                caps.desktop_sinks.append(sink_name)
                
        for line in res_sources.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                source_name = parts[1]
                if source_name.endswith(".monitor"):
                    caps.monitor_sources.append(source_name)
                else:
                    caps.mic_sources.append(source_name)
                    
        if caps.default_sink:
            monitor_name = caps.default_sink + ".monitor"
            if monitor_name in caps.monitor_sources:
                caps.default_sink_monitor = monitor_name
            elif caps.monitor_sources:
                caps.default_sink_monitor = caps.monitor_sources[0]
                
    except Exception:
        pass

    return caps
