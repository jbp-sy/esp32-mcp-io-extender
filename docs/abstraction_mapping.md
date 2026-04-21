# Workbench Abstraction Mapping

This repo provides two API levels:

1. Low-level bridge API (`EspGpioBridge`): direct protocol command access.
2. High-level workbench API (`HaloBoardWorkbench`): semantic operations + direct GP handles.

## Why this exists
Automation code should not build raw JSONL payloads directly. The workbench layer allows test flows to call intent-level operations while keeping pin/protocol details centralized.

## Core model
- `BoardSignal`: named semantic signal mapped to a pin and polarity.
- `HaloWorkbenchConfig`: collection of `signals` + optional `gp_aliases`.
- `HaloBoardWorkbench`: operations on top of a configured bridge.

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

## Safety and policy notes
- Firmware safety policy remains authoritative (blocked pins, UART reservation).
- Workbench methods rely on bridge errors for policy enforcement.
- Keep mapping files/data board-specific to avoid pin confusion across fixtures.

## Automation guidance
- Use semantic methods for test intent (`power_on`, `reset`) where possible.
- Use `gp(...)` access for fixture-specific operations.
- Keep signal naming stable across your automation suites.
