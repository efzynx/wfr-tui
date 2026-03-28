# wfr-tui

[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/efzynx/wfr-tui)

**wfr-tui** is a modern terminal-based user interface (TUI) for the renowned `wf-recorder` screen recording tool on Linux Wayland compositors (like Sway and Hyprland). Designed primarily for YouTube creators and video editors, it automates encoder detection (VAAPI), PulseAudio/PipeWire routing, and post-recording fixes with `ffmpeg`.

## Key Features

- **Hardware Acceleration Detection**: Automatically scans for `/dev/dri/renderD128` and parses `ffmpeg` enabled encoders to offer `h264_vaapi` or software fallback `libx264`.
- **Pure Virtual Audio Mixer**: Effortlessly records Desktop audio + Microphone simultaneously using an isolated `module-null-sink`. It prevents annoying audio feedback loops while providing a pristine recording!
- **Live Mic Monitoring & Metering**: Watch your microphone volume jump in real-time with our sleek UI progress bar. You can also toggle "Monitoring" on/off to hear your own mic without bleeding into the desktop audio track.
- **Modern Accordion TUI**: A highly responsive, focus-driven interface built with Textual. Panels gracefully collapse and expand (Accordion UI) to give you maximum breathing room.
- **Intelligent Presets**: Switch between recording types quickly (e.g., YouTube 1080p60 Hardware, Editing High Quality, Low Resource).
- **Metadata Fixing**: Automatically runs `ffmpeg -video_track_timescale 60k -c copy` after recording to fix common timestamping issues resulting in out-of-sync outputs on video editors.

## Requirements

Before running `wfr-tui`, make sure you have the following packages installed on your Linux distribution:
- `wf-recorder`
- `ffmpeg`
- `pactl` (pulse-utils or PipeWire's pulseaudio layer)
- `python >= 3.11`
- Optional: `vainfo` for extra diagnostic info.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/efzynx/wfr-tui.git
   cd wfr-tui
   ```
2. Run the installation script:
   ```bash
   ./install.sh
   ```
   *(This will automatically set up the virtual environment, install dependencies, and create a `wfr-tui` command in your `~/.local/bin` directory).*

3. Run the application directly from anywhere:
   ```bash
   wfr-tui
   ```
   *(Note: Make sure `~/.local/bin` is in your system's PATH)*

## Usage

When you open `wfr-tui`, you will be greeted by a robust terminal UI featuring an expandable accordion menu on the right.

### Keyboard Shortcuts
| Key | Action |
| --- | --- |
| `Space` / `Enter` | Start/Stop Recording |
| `Tab` / `Shift+Tab` | Change focus / Expand Accordion panels |
| `Up` / `Down` | Navigate within lists (Settings or Presets) |
| `q` | Request Quit |
| `F1` | Show Help message containing shortcuts |

### Setting Up a Recording
1. **Choose a preset** on the left panel (e.g., Target Usage).
2. Expand the **Recording Settings** accordion to set your **Target Directory** and verify **Encoder**.
3. Expand the **Audio Settings** accordion to determine your **Audio Mode** (e.g., *Desktop + Microphone (Loopback)*).
   - You can toggle Mute for both Desktop and Mic here.
   - You can also test your audio with the **Test Audio** button or toggle **Monitoring**.
4. Hit `Space` to start recording. Notice the background logs showing the loopback sink ID and subprocess metrics in the expanded **Status & Logs** panel.
5. Hit `Space` to stop. Wait a few seconds as the logger will show ffmpeg fixing the final output file before it turns back into `Status: Idle`. That means your recording is safe in your Videos directory!

## Configuration

Your preferences including last used preset and custom attributes are saved magically inside `~/.config/wfr-tui/config.json`. The app loads these settings automatically on the next launch!
