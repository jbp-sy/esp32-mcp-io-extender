# Skill: Verification and Safety

## Minimum verification
1. `python3 -m py_compile src/esp32_mcp_io_extender/bridge.py src/esp32_mcp_io_extender/mcp_server.py src/esp32_mcp_io_extender/cli.py src/esp32_mcp_io_extender/workbench.py`
2. If firmware changed: `cd firmware && pio run`
3. If hardware available: run `docs/agent_runbook.md`

## Safety invariants
- Blocked pins remain blocked unless intentionally revised.
- UART pins reserved by the active board profile remain blocked from generic gpio commands.
- Invalid input returns explicit error codes.
