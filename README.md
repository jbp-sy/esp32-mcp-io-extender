# ESP32 MCP IO Extender

ESP32-C3 firmware + Python library for GPIO/UART control over serial JSONL.

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

Alternative script names (same implementation):

```bash
esp32-mcp-io-extender --help
esp32-mcp-io-extender-mcp --help
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
```

Discovery behavior:
- `--list-devices`: list serial candidates from USB descriptor heuristics.
- `--list-devices --probe`: probe candidates and include protocol match status.
- `--probe`: probe and return only protocol-compatible devices.

The previous `esp32-mcp-io-extender` CLI entrypoint remains available and maps to
the same command implementation.

## MCP server usage
```bash
ESP_GPIO_PORT=/dev/tty.usbmodem1101 python -m esp32_mcp_io_extender.mcp_server
```

## Firmware setup
Build:
```bash
cd firmware
pio run
```

Flash:
```bash
cd firmware
pio run -t upload --upload-port /dev/tty.usbmodem1101
```

## Protocol and safety
- Protocol contract: [docs/serial_protocol.md](docs/serial_protocol.md)
- Validation checklist: [docs/validation.md](docs/validation.md)
- Deterministic runbook: [docs/agent_runbook.md](docs/agent_runbook.md)

Important defaults for current board profile:
- allowed GPIOs: `0,1,3,4,5,7`
- blocked/reserved include `2,6,8,9,10,18,19,20,21`
- UART bridge pins are fixed: `RX=20`, `TX=21`
