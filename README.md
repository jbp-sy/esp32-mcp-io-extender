# ESP32-C3 GPIO Controller for Codex (MCP)

This project turns an ESP-RS ESP32-C3 board into a GPIO co-processor that Codex can control via MCP.

It keeps the original architecture:
- firmware boundary: ESP32 serial JSON-line command handler
- host boundary: MCP server + serial transport
- operations boundary: Codex launches MCP locally over stdio

## Status
Usable for bench/debug workflows with:
- structured protocol responses and errors
- conservative board safety policy
- serial reconnect behavior on host
- CLI tester + MCP tools
- UART bridge tools (USB CDC host side -> target UART on GPIO20/GPIO21)

## Repository layout
- `firmware/` PlatformIO Arduino firmware
- `host/` MCP server + serial bridge + CLI tester
- `codex/` Codex MCP config templates
- `docs/serial_protocol.md` protocol spec
- `docs/validation.md` manual test flow
- `docs/architecture_note.md` current/target/changes note

## Board profile and safety policy
Profile id in firmware: `esp-rs-c3-photo-assumed-v1`

Assumptions based on provided board photos/silkscreen:
- Exposed labels include `GPIO0..GPIO10`, `GPIO20/RX`, `GPIO21/TX`, `GPIO9/BOOT`.
- Onboard I2C sensors appear tied to `GPIO6` (SCL) and `GPIO10` (SDA).
- USB data appears on `GPIO18`/`GPIO19`.

Default allowed GPIOs:
- `0`, `1`, `3`, `4`, `5`, `7`

Default blocked/reserved GPIOs:
- `2` (onboard RGB LED reservation)
- `6`, `10` (onboard I2C sensors)
- `8` (strap uncertainty)
- `9` (BOOT strap)
- `18`, `19` (USB D-/D+)
- `20`, `21` (UART RX/TX reserved)
- `11..17` (not exposed on this board profile)

If your hardware revision differs, update `policy_for_pin()` in `firmware/src/main.cpp`.

## Firmware setup (macOS/Linux)

Prerequisites:
- PlatformIO CLI (`pio`) installed
- USB data cable to board

Build:
```bash
cd firmware
pio run
```

Flash:
```bash
cd firmware
pio run -t upload
```

Serial monitor:
```bash
cd firmware
pio device monitor -b 115200
```

Expected boot event includes:
- `event: "boot"`
- protocol metadata (`protocol`, `protocol_version`)

## Host setup (macOS/Linux)

```bash
cd host
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional: list candidate serial ports
```bash
cd host
source .venv/bin/activate
python - <<'PY'
from esp_gpio_bridge import EspGpioBridge
for p in EspGpioBridge.list_candidate_ports():
    print(p)
PY
```

Run MCP server:
```bash
cd host
source .venv/bin/activate
ESP_GPIO_PORT=/dev/tty.usbmodemXXXX python mcp_gpio_server.py
```

Linux serial permission note (if needed):
```bash
sudo usermod -a -G dialout $USER
# log out/in after this change
```

## Codex MCP config
Use one of:
- `codex/config.toml` (generic template)
- `codex/config.macos.toml`
- `codex/config.linux.toml`

Required updates before use:
- set absolute `command`, `args`, `cwd`
- set `ESP_GPIO_PORT` (or leave empty with `ESP_GPIO_AUTO_PORT=1`)

## MCP tools exposed
Required tools:
- `gpio_ping`
- `gpio_info`
- `gpio_state`
- `gpio_set_mode`
- `gpio_write`
- `gpio_read`
- `gpio_adc_read`
- `gpio_pwm_write`

Additional tools:
- `gpio_digital_write_pulse`
- `gpio_transaction`
- `gpio_serial_ports`
- `gpio_uart_info`
- `gpio_uart_open`
- `gpio_uart_close`
- `gpio_uart_write_text`
- `gpio_uart_write_hex`
- `gpio_uart_read`

## CLI tester examples

```bash
cd host
source .venv/bin/activate
python gpio_cli.py --port /dev/tty.usbmodemXXXX ping
python gpio_cli.py --port /dev/tty.usbmodemXXXX info
python gpio_cli.py --port /dev/tty.usbmodemXXXX set-mode 4 output
python gpio_cli.py --port /dev/tty.usbmodemXXXX write 4 1
python gpio_cli.py --port /dev/tty.usbmodemXXXX write 4 0
python gpio_cli.py --port /dev/tty.usbmodemXXXX set-mode 3 input_pullup
python gpio_cli.py --port /dev/tty.usbmodemXXXX read 3
python gpio_cli.py --port /dev/tty.usbmodemXXXX adc 4
python gpio_cli.py --port /dev/tty.usbmodemXXXX pulse 4 --duration-ms 120
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-open --baud 115200
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-write-text "AT+GMR" --append-newline
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-read --max-bytes 256 --timeout-ms 100
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-close
```

## Manual validation sequence
See `docs/validation.md` for full flow.

Minimal sequence:
1. Connect board over USB.
2. Build + flash firmware.
3. Identify serial port.
4. Run host CLI `ping` + `info`.
5. Set one safe pin (example `4`) as output.
6. Toggle it with `write 1` then `write 0`.
7. Set one safe pin (example `3`) as input pullup and `read`.
8. Start MCP server and call `gpio_ping` from Codex.

## Protocol
Serial protocol details are in `docs/serial_protocol.md`.

Highlights:
- JSON lines over USB serial
- strict request/response by `id`
- structured errors: `error.code`, `error.message`, `error.details`
- protocol/version metadata in `meta`

## UART bridge usage
This firmware can be used as a USB-to-UART bridge for debugging targets.

Current pin mapping (fixed in firmware):
- ESP32 `GPIO21` = UART TX (connect to target RX)
- ESP32 `GPIO20` = UART RX (connect to target TX)
- GND must be shared between ESP32 board and target

Important:
- 3.3V logic only (do not connect to 5V UART directly)
- GPIO20/21 stay blocked from generic `gpio_*` operations and are reserved for `uart_*` commands

CLI example:
```bash
cd host
source .venv/bin/activate
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-open --baud 115200
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-write-text "help" --append-newline
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-read --max-bytes 256 --timeout-ms 200
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-close
```

## Physical UART disconnect / isolation options
Yes, you can physically gate UART lines when not in use.

Common options:
- Use a 2-pin jumper or DIP switch in series with TX and RX lines.
- Use tri-state bus transceivers with enable pin (for example `SN74LVC2T45`, `SN74LVC1T125`).
- Use analog switch ICs for signal gating (for example `TS5A23157`, `SN74CB3Q3257`).
- Use an external USB-UART module with jumpers and keep ESP32 bridge disabled in software.

A practical pattern:
1. Put TX/RX through a tri-state buffer.
2. Drive buffer `OE` from one ESP32 GPIO dedicated as `uart_enable`.
3. Keep `OE` disabled by default at boot.
4. Optionally add firmware logic to assert/deassert `uart_enable` around UART use (not implemented in this repo yet).

## Agent Runbook
For automation-oriented, deterministic validation steps (with expected pass/fail criteria), use:
- `docs/agent_runbook.md`

## Example Codex prompts
- "Call `gpio_info` and tell me which pins are allowed for ADC and PWM."
- "Set pin 4 to output and blink it 5 times using `gpio_write`."
- "Pulse pin 4 high for 150 ms using `gpio_digital_write_pulse`."
- "Run a `gpio_transaction` that sets pin 4 output then writes 1 then 0."

## Repository note
This directory is ready to become its own repository. If desired:
```bash
cd /path/to/esp32_gpio_codex
git init
git add .
git commit -m "Initial ESP32 GPIO MCP controller"
```
