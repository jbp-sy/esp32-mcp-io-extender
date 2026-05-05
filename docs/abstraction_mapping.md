# Workbench Abstraction Mapping

This repo provides two API levels:

1. Low-level bridge API (`EspGpioBridge`): direct protocol command access.
2. High-level workbench API (`HaloBoardWorkbench`): semantic operations + direct GP handles.
3. Host-side named endpoint API (`NamedGpioController`): JSON-configured GPIO aliases for CLI/MCP use.

## Why this exists
Automation code should not build raw JSONL payloads directly. The workbench layer allows test flows to call intent-level operations while keeping pin/protocol details centralized.

## Core model
- `BoardSignal`: named semantic signal mapped to a pin and polarity.
- `HaloWorkbenchConfig`: collection of `signals` + optional `gp_aliases`.
- `HaloBoardWorkbench`: operations on top of a configured bridge.
- `GpioEndpointConfig`: native JSON endpoint catalog loaded by CLI/MCP.
- `NamedGpioController`: resolves endpoint names to pins and calls existing bridge commands.

## Example mapping
```python
from esp32_mcp_io_extender import (
    BoardSignal,
    EspGpioBridge,
    HaloBoardWorkbench,
    HaloWorkbenchConfig,
    SerialConfig,
    SignalPolarity,
)

bridge = EspGpioBridge(SerialConfig(port="/dev/tty.usbmodem1101", auto_port=False))
cfg = HaloWorkbenchConfig(
    signals={
        "power": BoardSignal(name="power", pin=4, polarity=SignalPolarity.ACTIVE_HIGH),
        "reset": BoardSignal(name="reset", pin=5, polarity=SignalPolarity.ACTIVE_HIGH),
        "led_green": BoardSignal(name="led_green", pin=7, polarity=SignalPolarity.ACTIVE_LOW),
    },
    gp_aliases={"GP45": 4, "GP47": 7},
)
workbench = HaloBoardWorkbench(bridge, cfg)

workbench.power_on()
workbench.reset(duration_ms=120)
workbench.gp("GP45").set(1)
workbench.set_signal("led_green", True)
```

## MCP/CLI named endpoint mapping
Use native JSON endpoint configs when Codex or CLI should see fixture-specific
names such as `reset`, `button`, or `led_pwm` instead of raw GPIO numbers.

```json
{
  "version": 1,
  "endpoints": [
    {
      "name": "reset",
      "pin": 4,
      "capabilities": ["digital_out"],
      "mode": "output",
      "active_value": 0,
      "inactive_value": 1,
      "tools": [{"name": "reset_pulse", "operation": "pulse", "duration_ms": 120}]
    },
    {
      "name": "led_pwm",
      "pin": 7,
      "capabilities": ["pwm"],
      "mode": "output",
      "tools": [{"name": "led_pwm_write", "operation": "pwm_write"}]
    }
  ]
}
```

Start the MCP server with:

```bash
ESP_GPIO_ENDPOINT_CONFIG=./endpoints.json python -m esp32_mcp_io_extender.mcp_server
```

Set `ESP_GPIO_MCP_TOOL_SCOPE=named` or pass `--tool-scope named` when Codex
should only see named endpoint tools.

The repo includes a benchd-derived Halo profile conversion at
`configs/halo_syc_00048_r00_dvt2_endpoints.json`.

## Safety and policy notes
- Firmware safety policy remains authoritative (blocked pins, UART reservation).
- Workbench methods rely on bridge errors for policy enforcement.
- Keep mapping files/data board-specific to avoid pin confusion across fixtures.
- Named endpoint methods preflight configured pins against firmware-reported capabilities before mode changes or writes.

## Automation guidance
- Use semantic methods for test intent (`power_on`, `reset`) where possible.
- Use `gp(...)` access for fixture-specific operations.
- Keep signal naming stable across your automation suites.
