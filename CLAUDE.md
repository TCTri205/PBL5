# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Architecture Overview

This is a fruit classification system with edge inference. The architecture follows an **Edge-Inference + Remote-Monitoring** model:

- **Raspberry Pi (Edge)**: Runs `cam_stream.py` - captures images, runs ONNX model inference, controls hardware (conveyor, servo, sensor)
- **Laptop (Server)**: Runs `server.py` - WebSocket server that receives results, serves the dashboard UI

### Data Flow
```
Camera → Pi (Inference) → WebSocket → Laptop Server → Dashboard
                                      ↓
                              Hardware Control (servo/sensor/motor)
```

### Key Components

| File | Purpose |
|------|---------|
| `repo/laptop_server/server.py` | WebSocket server (aiohttp), handles Pi connections, dashboard, manual commands |
| `repo/pi_edge/cam_stream.py` | Main Pi pipeline: camera → inference → results → server |
| `repo/pi_edge/conveyor_controller.py` | Hardware control: L298N motor, E18-D80NK sensor, MG996R servo |
| `repo/pi_edge/fruit_classifier.py` | ONNX model inference wrapper |
| `repo/pi_edge/model/best.onnx` | YOLO model for fruit classification (cam/chanh/quyt) |

## Common Commands

```bash
# Install dependencies
pip install -r repo/requirements.txt

# Run tests
cd repo && python -m unittest discover -s tests -p "test_*.py" -v

# Run server (laptop)
python repo/start_server.py --host 0.0.0.0 --port 8765

# Run Pi client (manual control mode)
python repo/start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control

# Run Pi client (auto mode with model)
python repo/start_pi.py --server <LAPTOP_IP> --port 8765
```

## Hardware Pins

| Component | GPIO Pin | Notes |
|-----------|----------|-------|
| Motor Forward | 22 | L298N |
| Motor Backward | 23 | L298N (reverse direction) |
| Sensor | 17 | E18-D80NK (active-low) |
| Servo 1 (cam) | 5 | MG996R, 5s delay |
| Servo 2 (chanh) | 6 | MG996R, 8s delay |
| Servo 3 (quyt) | 26 | MG996R, 11s delay |

## Trick Mode (Manual Control)

A hidden feature for demos/testing without AI. Press keys 1-4 or arrow keys on the dashboard:

| Key | Label | Servo | Confidence Range |
|-----|-------|-------|------------------|
| 1 or ← | cam | Pin 5 | 82-98% |
| 2 or ↓ | chanh | Pin 6 | 82-98% |
| 3 or → | quyt | Pin 26 | 82-98% |
| 4 or ↑ | unknown | none | 35-55% |

## Project Structure

```
repo/
├── laptop_server/
│   ├── server.py          # WebSocket server
│   └── static/            # Dashboard HTML/CSS/JS
├── pi_edge/
│   ├── cam_stream.py      # Main Pi pipeline
│   ├── conveyor_controller.py  # Hardware control
│   ├── fruit_classifier.py     # ONNX inference
│   ├── model/best.onnx  # YOLO model
│   └── check_hardware.py
├── tests/                 # Unit tests
├── start_server.py        # Entry point
└── start_pi.py           # Entry point
```

## Testing Notes

- Tests use `unittest` with `aiohttp.test_utils.AioHTTPTestCase`
- Hardware classes have mock fallbacks when `TESTING=1` env var is set
- Run from `repo/` directory for proper imports