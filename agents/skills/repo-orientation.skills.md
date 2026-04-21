# Skill: Repo Orientation

## Purpose
Build a correct mental model before editing.

## Steps
1. Read `README.md` and `docs/architecture_note.md`.
2. Use boundaries:
- Firmware and protocol: `firmware/src/main.cpp`
- Host transport/errors: `host/esp_gpio_bridge.py`
- MCP exposure: `host/mcp_gpio_server.py`
- CLI diagnostics: `host/gpio_cli.py`
3. Preserve architecture boundaries.
