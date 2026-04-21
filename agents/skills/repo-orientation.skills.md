# Skill: Repo Orientation

## Purpose
Build a correct mental model before editing.

## Steps
1. Read `README.md` and `docs/architecture_note.md`.
2. Use boundaries:
- Firmware and protocol: `firmware/src/main.cpp`
- Python transport/errors: `src/esp32_mcp_io_extender/bridge.py`
- MCP exposure: `src/esp32_mcp_io_extender/mcp_server.py`
- CLI diagnostics: `src/esp32_mcp_io_extender/cli.py`
- Legacy wrappers only: `host/*.py`
3. Preserve architecture boundaries.
