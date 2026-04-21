from __future__ import annotations

import pytest

from esp32_mcp_io_extender.workbench import (
    BoardSignal,
    HaloBoardWorkbench,
    HaloWorkbenchConfig,
    SignalPolarity,
)


class _FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call(self, cmd: str, **kwargs):
        self.calls.append((cmd, kwargs))
        return {"cmd": cmd, **kwargs}


def _workbench() -> tuple[HaloBoardWorkbench, _FakeBridge]:
    b = _FakeBridge()
    cfg = HaloWorkbenchConfig(
        signals={
            "power": BoardSignal(name="power", pin=4),
            "reset": BoardSignal(name="reset", pin=5),
            "enable": BoardSignal(name="enable", pin=7, polarity=SignalPolarity.ACTIVE_LOW),
        },
        gp_aliases={"GP45": 4},
    )
    return HaloBoardWorkbench(b, cfg), b


def test_gp_handle_set_uses_write() -> None:
    wb, bridge = _workbench()

    wb.gp("GP45").set(1)

    assert bridge.calls[-1] == ("write", {"pin": 4, "value": 1})


def test_power_on_sets_mode_then_writes() -> None:
    wb, bridge = _workbench()

    wb.power_on()

    assert bridge.calls[0] == ("set_mode", {"pin": 4, "mode": "output"})
    assert bridge.calls[1] == ("write", {"pin": 4, "value": 1})


def test_active_low_signal_inverts_value() -> None:
    wb, bridge = _workbench()

    wb.set_signal("enable", True)

    assert bridge.calls[-1] == ("write", {"pin": 7, "value": 0})


def test_unknown_signal_raises() -> None:
    wb, _ = _workbench()
    with pytest.raises(KeyError):
        wb.set_signal("missing", True)
