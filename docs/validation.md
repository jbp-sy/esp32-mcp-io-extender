# Validation Procedure

## 1) Build firmware
```bash
cd firmware
pio run
```

## 2) Flash firmware
```bash
cd firmware
pio run -t upload
```

## 3) Identify serial device
macOS:
```bash
ls /dev/tty.usbmodem*
```
Linux:
```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

## 4) Host environment
```bash
cd host
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5) CLI smoke checks
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
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-open --baud 115200
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-info
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-read --max-bytes 64 --timeout-ms 50
python gpio_cli.py --port /dev/tty.usbmodemXXXX uart-close
```

## 6) MCP server run
```bash
cd host
source .venv/bin/activate
ESP_GPIO_PORT=/dev/tty.usbmodemXXXX python mcp_gpio_server.py
```

## 7) MCP tool checks from Codex
- `gpio_ping`
- `gpio_info`
- `gpio_set_mode` (`pin=4`, `mode="output"`)
- `gpio_write` (`pin=4`, `value=1`, then `0`)
- `gpio_read` (`pin=3` after input mode)
- `gpio_adc_read` (safe ADC pin)
- `gpio_uart_info`
- `gpio_uart_open` (`baud=115200`)
- `gpio_uart_read` (`max_bytes=64`, `timeout_ms=50`)
- `gpio_uart_close`

## Notes
- Expected blocked behavior: attempts on `GPIO9`, `GPIO18`, `GPIO19`, `GPIO20`, `GPIO21` should return `pin_blocked`.
- Expected UART guard behavior: `uart_read`/`uart_write` before `uart_open` should return `uart_not_open`.
- If hardware is not attached, host checks can still validate import/syntax and tool registration.
