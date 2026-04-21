# Architecture Note

## Current state (from starter)
- Firmware accepted JSON-line commands and performed direct GPIO operations.
- Host FastMCP server proxied a small set of commands via pyserial.
- Minimal safety policy and limited reconnect/error behavior.

## Target state
- Keep architecture boundaries:
  - Firmware: serial command handler + board safety policy.
  - Host: MCP server + serial transport reliability.
  - Operations: Codex launches MCP locally over stdio.
- Be bench-usable with explicit guardrails and predictable failures.

## Changes made

### Firmware
- Added protocol metadata (`protocol`, `protocol_version`, `firmware_version`) on all responses.
- Added structured error object with `code`, `message`, `details`.
- Added ESP-RS ESP32-C3 board profile and default blocked pin policy.
- Added capability checks by operation (`digital_in`, `digital_out`, `adc`, `pwm`).
- Added required commands and aliases:
  - `ping`, `info`, `state`
  - `set_mode`/`pinMode`
  - `write`/`digitalWrite`
  - `read`/`digitalRead`
  - `adc_read`/`analogRead`
  - `pwm_write`/`analogWrite`
- Added optional commands:
  - `digital_write_pulse`
  - `batch` (`transaction` alias)
  - `uart_info`, `uart_open`, `uart_close`, `uart_write`, `uart_read`
- Added input line-length guard (`512` bytes).
- Added UART bridge state/config handling on reserved pins (`GPIO20`/`GPIO21`).

### Host
- Split transport logic into reusable `esp_gpio_bridge.py`.
- Added serial reconnect retries + backoff and optional auto-port detection.
- Added explicit firmware/device error surfacing.
- Kept required MCP tools and added optional tools:
  - `gpio_digital_write_pulse`
  - `gpio_transaction`
  - `gpio_serial_ports`
  - `gpio_uart_*` toolset for UART debugging workflows
- Added standalone CLI tester (`gpio_cli.py`) for bench diagnostics.

### Documentation/config
- Rewrote README with full setup and validation flow.
- Added serial protocol reference doc.
- Added macOS/Linux Codex MCP config templates.

## Result
The project remains JSON-lines over USB serial with FastMCP host tooling, now with explicit safety policy, protocol versioning, stronger error semantics, reconnect behavior, and a practical test flow.
