# ESP32 MCP IO Extender

ESP32 firmware + Python library for GPIO/UART control over serial JSONL.

This repo is the source of truth for:
- firmware protocol and safety policy,
- Python transport abstraction (`EspGpioBridge`),
- optional MCP server entrypoint,
- higher-level workbench abstraction (`HaloBoardWorkbench`).

## Repository layout
- `firmware/` PlatformIO Arduino firmware
- `src/esp32_mcp_io_extender/` installable Python package
- `docs/serial_protocol.md` protocol contract
- `docs/abstraction_mapping.md` high-level abstraction model
- `docs/agent_runbook.md` deterministic validation flow

## Install the Python library
From git (recommended for cross-repo integration):

```bash
pip install 'esp32-mcp-io-extender @ git+https://github.com/jbp-sy/esp32-mcp-io-extender.git@main'
```

With MCP support:

```bash
pip install 'esp32-mcp-io-extender[mcp] @ git+https://github.com/jbp-sy/esp32-mcp-io-extender.git@main'
```

Local dev install:

```bash
pip install -e .
# optional test/dev deps
pip install -e '.[dev,mcp]'
```

## CLI setup
Use a local virtual environment so the CLI scripts are installed on your PATH:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[mcp]'
esp32mcpio --help
```

If your shell cannot find the scripts, run the module directly:

```bash
python -m esp32_mcp_io_extender.cli --help
python -m esp32_mcp_io_extender.mcp_server --help
```

## Python usage
### Low-level bridge API
```python
from esp32_mcp_io_extender import EspGpioBridge, SerialConfig

bridge = EspGpioBridge(SerialConfig(port="/dev/tty.usbmodem1101", auto_port=False))
bridge.call("set_mode", pin=4, mode="output")
bridge.call("write", pin=4, value=1)
```

### Host-side UART PTY daemon API
```python
from esp32_mcp_io_extender import uart_pty_start, uart_pty_status, uart_pty_stop

uart_pty_start(path="/tmp/uart.esp32", name="esp32")
print(uart_pty_status(path="/tmp/uart.esp32"))
uart_pty_stop(path="/tmp/uart.esp32")
```

### High-level workbench API
```python
from esp32_mcp_io_extender import (
    BoardSignal,
    EspGpioBridge,
    HaloBoardWorkbench,
    HaloWorkbenchConfig,
    SerialConfig,
)

bridge = EspGpioBridge(SerialConfig(port="/dev/tty.usbmodem1101", auto_port=False))
config = HaloWorkbenchConfig(
    signals={
        "power": BoardSignal(name="power", pin=4),
        "reset": BoardSignal(name="reset", pin=5),
    },
    gp_aliases={"GP45": 4},
)

workbench = HaloBoardWorkbench(bridge, config)
workbench.power_on()
workbench.reset()
workbench.gp("GP45").set(1)
```

See [docs/abstraction_mapping.md](docs/abstraction_mapping.md) for mapping guidance.

## CLI usage
After install:

```bash
esp32mcpio --help
esp32mcpio --list-devices
esp32mcpio --list-devices --probe
esp32mcpio --probe
esp32mcpio --port /dev/tty.usbmodem1101 --list-capabilities
esp32mcpio --port /dev/tty.usbmodem1101 ping
esp32mcpio --port /dev/tty.usbmodem1101 gpio pulse --pin 4 --state 1 --duration-ms 100
esp32mcpio --port /dev/tty.usbmodem1101 uart open --baud 115200
esp32mcpio --port /dev/tty.usbmodem1101 uart pty start --path /tmp/uart.esp32 --name esp32
esp32mcpio uart pty status --path /tmp/uart.esp32
esp32mcpio uart pty stop --path /tmp/uart.esp32
```

Discovery behavior:
- `--list-devices`: list serial candidates from USB descriptor heuristics.
- `--list-devices --probe`: probe candidates and include protocol match status.
- `--probe`: probe and return only protocol-compatible devices.

UART command distinction:
- `uart open|close|write-text|write-hex|read`: firmware UART bridge control.
- `uart pty start|stop|status`: host PTY daemon lifecycle using explicit `--path`.

## MCP server usage
```bash
ESP_GPIO_PORT=/dev/tty.usbmodem1101 python -m esp32_mcp_io_extender.mcp_server
```

## Firmware setup
Build:
```bash
cd firmware
pio run
# or build the S3 profile:
pio run -e esp32-s3-fh4r2
```

Flash:
```bash
cd firmware
pio run -t upload --upload-port /dev/tty.usbmodem1101
# or flash the S3 profile:
pio run -e esp32-s3-fh4r2 -t upload --upload-port /dev/tty.usbmodem1101
```

## Protocol and safety
- Protocol contract: [docs/serial_protocol.md](docs/serial_protocol.md)
- Validation checklist: [docs/validation.md](docs/validation.md)
- Deterministic runbook: [docs/agent_runbook.md](docs/agent_runbook.md)

Important defaults by board profile:
- `esp-rs-c3-photo-assumed-v1` (default env `esp32-c3-devkitm-1`):
  - allowed GPIOs: `0,1,3,4,5,7`
  - blocked/reserved include `2,6,8,9,10,18,19,20,21`
  - UART bridge pins are fixed: `RX=20`, `TX=21`
- `esp32-s3-fh4r2-safe-v1` (env `esp32-s3-fh4r2`):
  - allowed GPIOs: `1,2,4,5,6,7,8,9,10,11,12,13,14,15,18,21`
  - blocked/reserved include boot straps, USB pins (`19`,`20`), UART bridge pins (`16`,`17`), and flash/PSRAM internal pins (`26..32`)
  - UART bridge pins are fixed: `RX=16`, `TX=17`

The S3 profile is intentionally conservative for bench safety. If a specific S3
board revision exposes additional safe GPIOs, extend the profile and bench YAML
together.
