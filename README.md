# CRYSTAL System Monitor

A lightweight, glassmorphism-style desktop widget for Windows 11 that displays real-time system metrics with a frosted glass appearance using Windows DWM Acrylic blur.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%2011-0078D4?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Real-time monitoring** — CPU, RAM, Disk, Network (↑↓), GPU
- **Glassmorphism UI** — Windows DWM Acrylic blur (real frosted glass, not fake)
- **Arc gauges** — RAM and GPU displayed as animated circular gauges
- **Responsive layout** — fonts, bars, and gauges all scale when you resize
- **Borderless & always-on-top** — floats cleanly over any window
- **Draggable** — click and drag anywhere to reposition
- **Resizable** — drag bottom-right corner
- **Windows startup** — includes `launch.vbs` for auto-start on login

## Preview

```
  ╭─────────────────────────────╮
  │  ╭── RAM ──╮  ╭── GPU ──╮  │
  │  │  6.2/   │  │  18%    │  │
  │  │  16G    │  │         │  │
  │  ╰─────────╯  ╰─────────╯  │
  │                             │
  │  CPU  ████████░░  42%       │
  │  DISK ████░░░░░░  234/476G  │
  │  ↑NET ░░░░░░░░░░  12K/s     │
  │  ↓NET █████░░░░░  1.4M/s    │
  │                             │
  │  14:32:07    up 3h 45m      │
  ╰─────────────────────────────╯
```

## Requirements

- Windows 10 / 11
- Python 3.10+
- Intel / NVIDIA / AMD GPU (GPU monitoring via WMI)

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/PanithanNanti/crystal-sysmonitor.git
cd crystal-sysmonitor

# 2. Install dependencies
pip install psutil wmi pywin32

# 3. Run
pythonw widget.py
```

## Controls

| Action | How |
|--------|-----|
| Move | Click and drag anywhere on the widget |
| Resize | Drag the bottom-right corner grip |
| Close | Click the red ✕ button (top-right) |

## Auto-start on Windows Login

Copy `launch.vbs` to your Windows Startup folder:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

Or run this in PowerShell:
```powershell
Copy-Item launch.vbs "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\crystal-sysmonitor.vbs"
```

> The script waits 8 seconds after login before launching — giving time for Google Drive and other cloud storage to mount.

## Configuration

Edit the constants near the top of `widget.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `W0, H0` | `270, 360` | Default window size |
| `MIN_W, MIN_H` | `220, 280` | Minimum window size |
| `TICK_MS` | `80` | Animation tick (ms) |

To adjust transparency, change the acrylic tint in `__init__`:
```python
_apply_acrylic(hwnd, 0x55FFFFFF)  # 0xAA = opacity (00=clear, FF=opaque)
```

## Tech Stack

- **tkinter** — UI rendering (Canvas-based, no external GUI lib)
- **psutil** — CPU, RAM, Disk, Network metrics
- **wmi** — GPU utilization via Windows Performance Counters
- **ctypes / DWM API** — Real Windows Acrylic blur effect

## License

MIT
