# Skill: Verification and Safety

## Minimum verification
1. `python3 -m py_compile host/esp_gpio_bridge.py host/mcp_gpio_server.py host/gpio_cli.py`
2. If firmware changed: `cd firmware && pio run`
3. If hardware available: run `docs/agent_runbook.md`

## Safety invariants
- Blocked pins remain blocked unless intentionally revised.
- UART pins `GPIO20`/`GPIO21` remain reserved from generic gpio commands.
- Invalid input returns explicit error codes.
