# ESP32 GPIO Serial Protocol (JSON Lines)

## Transport
- Physical link: USB CDC serial
- Encoding: UTF-8 JSON, one object per line (`\n`)
- Baud rate: `115200`
- Request/response pattern: host sends one request, firmware returns one response with matching `id`

## Request shape

```json
{
  "id": "uuid-or-string",
  "cmd": "set_mode",
  "pin": 4,
  "mode": "output"
}
```

Fields:
- `id` optional but recommended; host always sends it.
- `cmd` required command string.
- Other fields depend on command.

## Success response shape

```json
{
  "ok": true,
  "id": "same-id",
  "result": {"pin": 4, "mode": "output"},
  "meta": {
    "protocol": "esp32-gpio-jsonl",
    "protocol_version": "1.1.0",
    "firmware_version": "0.2.0",
    "board_id": "esp-rs-esp32-c3",
    "board_profile": "esp-rs-c3-photo-assumed-v1",
    "uptime_ms": 12345
  }
}
```

`meta.board_id` and `meta.board_profile` are target-specific and vary by build profile.

## Error response shape

```json
{
  "ok": false,
  "id": "same-id-if-provided",
  "error": {
    "code": "pin_blocked",
    "message": "pin is blocked by board safety policy",
    "details": {
      "pin": 9,
      "reason": "boot_button_strap"
    }
  },
  "meta": {
    "protocol": "esp32-gpio-jsonl",
    "protocol_version": "1.1.0"
  }
}
```

## Boot event
When serial opens, firmware emits one informational line:

```json
{"ok":true,"event":"boot","result":{"board":"<board_id>"},"meta":{...}}
```

Host ignores `event` lines during request/response matching.

## Commands
Primary commands:
- `ping`
- `info`
- `state`
- `set_mode` (`pinMode` alias)
- `write` (`digitalWrite` alias)
- `read` (`digitalRead` alias)
- `adc_read` (`analogRead` alias)
- `pwm_write` (`analogWrite` alias)
- `digital_write_pulse`
- `batch` (`transaction` alias)
- `uart_info`
- `uart_open`
- `uart_close`
- `uart_write`
- `uart_read`

### `ping`
Request:
```json
{"cmd":"ping"}
```

### `info`
Returns board/chip metadata and policy:
- `policy.allowed_pins`
- `policy.blocked_pins`
- `policy.pin_capabilities`
- `policy.named_pins`

Host tools use this policy as the capability source for `esp32mcpio
--list-capabilities` and for preflight checks before GPIO operations. Firmware
policy remains authoritative if host preflight is bypassed.

### `state`
Returns tracked runtime state:
- `pin_modes`
- `digital`
- `pwm`
- `policy`

### `set_mode`
Request:
```json
{"cmd":"set_mode","pin":4,"mode":"output"}
```
Modes:
- `input`
- `input_pullup`
- `input_pulldown`
- `output`
- `output_open_drain`

### `write`
Request:
```json
{"cmd":"write","pin":4,"value":1}
```
Requirements:
- pin must be policy-allowed for digital output
- mode must already be output/open-drain

### `read`
Request:
```json
{"cmd":"read","pin":4}
```

### `adc_read`
Request:
```json
{"cmd":"adc_read","pin":4}
```

### `pwm_write`
Request:
```json
{"cmd":"pwm_write","pin":4,"value":128,"freq":5000,"resolution":8}
```
Limits:
- `resolution`: `1..14`
- `freq`: `1..40000`
- `value`: `0..(2^resolution-1)`

### `digital_write_pulse`
Request:
```json
{"cmd":"digital_write_pulse","pin":4,"value":1,"duration_ms":100,"restore":0}
```

### `batch`
Request:
```json
{
  "cmd":"batch",
  "ops":[
    {"cmd":"set_mode","pin":4,"mode":"output"},
    {"cmd":"write","pin":4,"value":1}
  ]
}
```
Response `result` is an array of per-op responses. If any op fails, top-level response has `ok=false` and `error.code=batch_failed`.

### `uart_info`
Request:
```json
{"cmd":"uart_info"}
```
Returns open/closed state and supported pins (`supported_rx_pin`, `supported_tx_pin`) for the active board profile.

### `uart_open`
Request:
```json
{
  "cmd":"uart_open",
  "baud":115200,
  "rx_pin":20,
  "tx_pin":21,
  "data_bits":8,
  "parity":"N",
  "stop_bits":1,
  "timeout_ms":20
}
```
Notes:
- Current firmware accepts only the board-profile UART pin pair returned by `uart_info` (`supported_rx_pin`, `supported_tx_pin`).
- Current profiles:
  - `esp-rs-c3-photo-assumed-v1`: `RX=20`, `TX=21`
  - `esp32-s3-fh4r2-safe-v1`: `RX=16`, `TX=17`
- Supported frame formats: `8N1`, `8N2`, `8E1`, `8O1`, `7N1`, `7E1`, `7O1`.

### `uart_close`
Request:
```json
{"cmd":"uart_close"}
```

### `uart_write`
Write text payload:
```json
{"cmd":"uart_write","text":"AT+GMR\\r\\n","drain":true}
```

Write hex payload:
```json
{"cmd":"uart_write","hex":"41542B474D520D0A","drain":true}
```

Optional fields:
- `append_newline` boolean (for text writes)
- `drain` boolean (default `true`)

### `uart_read`
Request:
```json
{"cmd":"uart_read","max_bytes":128,"timeout_ms":20}
```
Response includes:
- `bytes`
- `text` (ASCII preview, non-printable replaced with `.`)
- `hex`
- `truncated`
- `remaining_available`

## Common error codes
- `invalid_json`
- `line_too_long`
- `unknown_command`
- `missing_pin`
- `missing_pin_or_mode`
- `missing_pin_or_value`
- `pin_out_of_profile`
- `pin_blocked`
- `capability_not_allowed`
- `mode_not_set`
- `mode_not_output`
- `invalid_mode`
- `invalid_resolution`
- `invalid_frequency`
- `value_out_of_range`
- `batch_failed`
- `uart_not_open`
- `unsupported_uart_pins`
- `invalid_uart_baud`
- `invalid_uart_config`
- `missing_uart_payload`
- `uart_payload_too_large`
- `invalid_uart_hex`
- `invalid_uart_read_size`
