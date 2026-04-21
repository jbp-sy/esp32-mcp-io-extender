# Agent Runbook (Deterministic Validation)

This runbook is designed for an autonomous agent to bring up and verify the board with minimal ambiguity.

## Preconditions
- USB-connected ESP32-C3 board.
- Working directory: project root.
- Python venv exists in `host/.venv`.
- PlatformIO available (`pio`) or `firmware/.venv_pio` with `platformio` installed.

## 1) Discover candidate serial ports

```bash
cd host
source .venv/bin/activate
python - <<'PY'
from esp_gpio_bridge import EspGpioBridge
for p in EspGpioBridge.list_candidate_ports():
    print(f"{p.device}\t{p.description}\tscore={p.score}")
PY
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
```

Option B (`platformio` in venv):
```bash
cd firmware
source .venv_pio/bin/activate
python -m platformio run
python -m platformio run -t upload --upload-port "$ESP_PORT"
```

Pass criteria:
- Build exits `0`.
- Upload exits `0`.

## 4) GPIO + protocol smoke test

```bash
cd host
source .venv/bin/activate
python gpio_cli.py --port "$ESP_PORT" ping
python gpio_cli.py --port "$ESP_PORT" info
python gpio_cli.py --port "$ESP_PORT" set-mode 4 output
python gpio_cli.py --port "$ESP_PORT" write 4 1
python gpio_cli.py --port "$ESP_PORT" write 4 0
python gpio_cli.py --port "$ESP_PORT" set-mode 3 input_pullup
python gpio_cli.py --port "$ESP_PORT" read 3
python gpio_cli.py --port "$ESP_PORT" adc 1
```

Pass criteria:
- `ping` response has `ok: true` and `meta.protocol == "esp32-gpio-jsonl"`.
- `info` includes `policy.allowed_pins` and `policy.blocked_pins`.
- GPIO set/write/read/adc commands return structured JSON and no CLI error.

## 5) UART bridge smoke test

```bash
cd host
source .venv/bin/activate
python gpio_cli.py --port "$ESP_PORT" uart-info
python gpio_cli.py --port "$ESP_PORT" uart-open --baud 115200
python gpio_cli.py --port "$ESP_PORT" uart-write-text "uart test" --append-newline
python gpio_cli.py --port "$ESP_PORT" uart-read --max-bytes 64 --timeout-ms 50
python gpio_cli.py --port "$ESP_PORT" uart-close
```

Pass criteria:
- `uart-open` returns `open: true` with `rx_pin: 20` and `tx_pin: 21`.
- `uart-close` returns `closed: true`.
- `uart-read` returns structured payload (`bytes`, `hex`, `text`).

## 6) Safety checks (must fail)

```bash
cd host
source .venv/bin/activate
python gpio_cli.py --port "$ESP_PORT" set-mode 21 output
python gpio_cli.py --port "$ESP_PORT" write 9 1
python gpio_cli.py --port "$ESP_PORT" uart-read --max-bytes 16 --timeout-ms 20
```

Expected failures:
- `set-mode 21 output` -> `pin_blocked`
- `write 9 1` -> `pin_blocked`
- `uart-read` when UART is closed -> `uart_not_open`

## 7) MCP server verification

```bash
cd host
source .venv/bin/activate
ESP_GPIO_PORT="$ESP_PORT" python - <<'PY'
import mcp_gpio_server
names = sorted(mcp_gpio_server.mcp._tool_manager._tools.keys())
print("tool_count", len(names))
for n in names:
    print(n)
PY
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

## 8) Report template for agent handoff

Include:
- exact port used
- build/upload command + exit status
- each smoke test command + pass/fail
- each safety test command + expected failure observed
- unresolved assumptions (pin mapping, connected target, voltage levels)
