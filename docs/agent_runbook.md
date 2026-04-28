# Agent Runbook (Deterministic Validation)

This runbook is designed for an autonomous agent to bring up and verify the board with minimal ambiguity.

## Preconditions
- USB-connected supported board:
  - ESP32-C3 profile (`esp32-c3-devkitm-1`)
  - ESP32-S3 profile (`esp32-s3-fh4r2`)
- Working directory: project root.
- Python venv exists in `.venv` with `pip install -e '.[dev,mcp]'`.
- PlatformIO available (`pio`) or `firmware/.venv_pio` with `platformio` installed.

## 1) Discover candidate serial ports

```bash
source .venv/bin/activate
esp32mcpio --list-devices
esp32mcpio --list-devices --probe
```

Pass criteria:
- At least one candidate port is listed.
- Prefer ports with ESP32 descriptors and/or VID:PID `303A:1001`.

## 2) Set target port

```bash
export ESP_PORT=/dev/cu.usbmodem1101
# Linux example: export ESP_PORT=/dev/ttyACM0
```

## 3) Build and flash firmware

Option A (`pio`):
```bash
cd firmware
pio run
pio run -t upload --upload-port "$ESP_PORT"
# S3 profile:
pio run -e esp32-s3-fh4r2
pio run -e esp32-s3-fh4r2 -t upload --upload-port "$ESP_PORT"
```

Option B (`platformio` in venv):
```bash
cd firmware
source .venv_pio/bin/activate
python -m platformio run
python -m platformio run -t upload --upload-port "$ESP_PORT"
# S3 profile:
python -m platformio run -e esp32-s3-fh4r2
python -m platformio run -e esp32-s3-fh4r2 -t upload --upload-port "$ESP_PORT"
```

Pass criteria:
- Build exits `0`.
- Upload exits `0`.

## 4) GPIO + protocol smoke test

```bash
source .venv/bin/activate
esp32mcpio --port "$ESP_PORT" ping
esp32mcpio --port "$ESP_PORT" info
esp32mcpio --port "$ESP_PORT" --list-capabilities
esp32mcpio --port "$ESP_PORT" gpio set-mode --pin 4 --mode output
esp32mcpio --port "$ESP_PORT" gpio write --pin 4 --state 1
esp32mcpio --port "$ESP_PORT" gpio write --pin 4 --state 0
esp32mcpio --port "$ESP_PORT" gpio set-mode --pin 3 --mode input_pullup
esp32mcpio --port "$ESP_PORT" gpio read --pin 3
esp32mcpio --port "$ESP_PORT" gpio adc --pin 1
```

Pass criteria:
- `ping` response has `ok: true` and `meta.protocol == "esp32-gpio-jsonl"`.
- `info` includes `policy.allowed_pins` and `policy.blocked_pins`.
- GPIO set/write/read/adc commands return structured JSON and no CLI error.

## 5) UART bridge smoke test

```bash
source .venv/bin/activate
esp32mcpio --port "$ESP_PORT" uart info
esp32mcpio --port "$ESP_PORT" uart open --baud 115200
esp32mcpio --port "$ESP_PORT" uart write-text "uart test" --append-newline
esp32mcpio --port "$ESP_PORT" uart read --max-bytes 64 --timeout-ms 50
esp32mcpio --port "$ESP_PORT" uart close
```

Pass criteria:
- `uart-open` returns `open: true` and `rx_pin`/`tx_pin` matching `uart_info.supported_rx_pin`/`supported_tx_pin`.
- `uart-close` returns `closed: true`.
- `uart-read` returns structured payload (`bytes`, `hex`, `text`).

## 6) UART PTY daemon smoke test (host-side)

```bash
source .venv/bin/activate
esp32mcpio --port "$ESP_PORT" uart pty start --path /tmp/uart.esp32 --name esp32
esp32mcpio uart pty status --path /tmp/uart.esp32
ls -l /tmp/uart.esp32
# optional: interact with your own serial client against /tmp/uart.esp32
esp32mcpio uart pty stop --path /tmp/uart.esp32
```

Pass criteria:
- `start` returns `running: true` with `path` and daemon `pid`.
- `status` reports `running: true` while daemon is active.
- `/tmp/uart.esp32` exists during runtime and is removed after `stop`.
- `stop` returns `stopped: true`.

## 7) Safety checks (must fail)

```bash
source .venv/bin/activate
esp32mcpio --port "$ESP_PORT" gpio set-mode --pin 20 --mode output
esp32mcpio --port "$ESP_PORT" gpio write --pin 9 --state 1
esp32mcpio --port "$ESP_PORT" uart read --max-bytes 16 --timeout-ms 20
```

Expected failures:
- `set-mode 20 output` -> `pin_blocked`
- `write 9 1` -> `pin_blocked`
- `uart-read` when UART is closed -> `uart_not_open`

## 8) MCP server verification

```bash
source .venv/bin/activate
ESP_GPIO_PORT="$ESP_PORT" python -m esp32_mcp_io_extender.mcp_server
```

Required tool names must include:
- `gpio_ping`
- `gpio_info`
- `gpio_state`
- `gpio_set_mode`
- `gpio_write`
- `gpio_read`
- `gpio_adc_read`
- `gpio_pwm_write`
- `gpio_uart_info`
- `gpio_uart_open`
- `gpio_uart_close`
- `gpio_uart_write_text`
- `gpio_uart_write_hex`
- `gpio_uart_read`

## 9) Report template for agent handoff

Include:
- exact port used
- build/upload command + exit status
- each smoke test command + pass/fail
- each safety test command + expected failure observed
- unresolved assumptions (pin mapping, connected target, voltage levels)
