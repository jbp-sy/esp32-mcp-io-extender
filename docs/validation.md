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
Use passive detection first, then probe candidates when it is safe to open the
serial ports:

```bash
esp32mcpio --list-devices
esp32mcpio --list-devices --probe
```

## 4) Host environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,mcp]'
```

## 5) CLI smoke checks
```bash
source .venv/bin/activate
esp32mcpio --port /dev/tty.usbmodemXXXX ping
esp32mcpio --port /dev/tty.usbmodemXXXX info
esp32mcpio --port /dev/tty.usbmodemXXXX --list-capabilities
esp32mcpio --port /dev/tty.usbmodemXXXX gpio set-mode --pin 4 --mode output
esp32mcpio --port /dev/tty.usbmodemXXXX gpio write --pin 4 --state 1
esp32mcpio --port /dev/tty.usbmodemXXXX gpio write --pin 4 --state 0
esp32mcpio --port /dev/tty.usbmodemXXXX gpio set-mode --pin 3 --mode input_pullup
esp32mcpio --port /dev/tty.usbmodemXXXX gpio read --pin 3
esp32mcpio --port /dev/tty.usbmodemXXXX gpio adc --pin 4
esp32mcpio --port /dev/tty.usbmodemXXXX uart open --baud 115200
esp32mcpio --port /dev/tty.usbmodemXXXX uart info
esp32mcpio --port /dev/tty.usbmodemXXXX uart read --max-bytes 64 --timeout-ms 50
esp32mcpio --port /dev/tty.usbmodemXXXX uart close
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
