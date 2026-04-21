from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .bridge import EspGpioBridge


class SignalPolarity(str, Enum):
    ACTIVE_HIGH = "active_high"
    ACTIVE_LOW = "active_low"


@dataclass(slots=True)
class BoardSignal:
    name: str
    pin: int
    polarity: SignalPolarity = SignalPolarity.ACTIVE_HIGH
    default_mode: str = "output"


@dataclass(slots=True)
class HaloWorkbenchConfig:
    signals: dict[str, BoardSignal] = field(default_factory=dict)
    gp_aliases: dict[str, int] = field(default_factory=dict)

    def signal(self, name: str) -> BoardSignal:
        key = name.strip().lower()
        try:
            return self.signals[key]
        except KeyError as exc:
            raise KeyError(f"unknown signal: {name}") from exc

    def resolve_gp_pin(self, alias_or_pin: str | int) -> int:
        if isinstance(alias_or_pin, int):
            return alias_or_pin

        token = alias_or_pin.strip().upper()
        if token in self.gp_aliases:
            return self.gp_aliases[token]

        if token.startswith("GP") and token[2:].isdigit():
            return int(token[2:])

        if token.isdigit():
            return int(token)

        raise KeyError(f"unknown GP alias: {alias_or_pin}")


class GpioHandle:
    def __init__(self, bridge: EspGpioBridge, pin: int):
        self._bridge = bridge
        self.pin = pin

    def set_mode(self, mode: str) -> dict[str, Any]:
        return self._bridge.call("set_mode", pin=self.pin, mode=mode)

    def set(self, value: int) -> dict[str, Any]:
        return self._bridge.call("write", pin=self.pin, value=1 if value else 0)

    def get(self) -> dict[str, Any]:
        return self._bridge.call("read", pin=self.pin)

    def pulse(self, duration_ms: int = 100, pulse_value: int = 1, restore: int = 0) -> dict[str, Any]:
        return self._bridge.call(
            "digital_write_pulse",
            pin=self.pin,
            value=1 if pulse_value else 0,
            duration_ms=duration_ms,
            restore=1 if restore else 0,
        )


class HaloBoardWorkbench:
    """Higher-level workbench API over EspGpioBridge.

    v1 supports both semantic signal operations and direct GP handle access.
    """

    def __init__(self, bridge: EspGpioBridge, config: HaloWorkbenchConfig):
        self.bridge = bridge
        self.config = config

    def gp(self, alias_or_pin: str | int) -> GpioHandle:
        return GpioHandle(self.bridge, self.config.resolve_gp_pin(alias_or_pin))

    def set_signal(self, signal_name: str, enabled: bool) -> dict[str, Any]:
        signal = self.config.signal(signal_name)
        logical_on = 1 if enabled else 0
        value = logical_on if signal.polarity == SignalPolarity.ACTIVE_HIGH else (1 - logical_on)
        self.bridge.call("set_mode", pin=signal.pin, mode=signal.default_mode)
        return self.bridge.call("write", pin=signal.pin, value=value)

    def pulse_signal(self, signal_name: str, duration_ms: int = 100) -> dict[str, Any]:
        signal = self.config.signal(signal_name)
        active_value = 1 if signal.polarity == SignalPolarity.ACTIVE_HIGH else 0
        restore_value = 0 if active_value == 1 else 1
        self.bridge.call("set_mode", pin=signal.pin, mode=signal.default_mode)
        return self.bridge.call(
            "digital_write_pulse",
            pin=signal.pin,
            value=active_value,
            duration_ms=duration_ms,
            restore=restore_value,
        )

    # Semantic operations for common automation flows.
    def power_on(self) -> dict[str, Any]:
        return self.set_signal("power", True)

    def power_off(self) -> dict[str, Any]:
        return self.set_signal("power", False)

    def reset(self, duration_ms: int = 120) -> dict[str, Any]:
        return self.pulse_signal("reset", duration_ms=duration_ms)


def default_demo_workbench(bridge: EspGpioBridge) -> HaloBoardWorkbench:
    config = HaloWorkbenchConfig(
        signals={
            "power": BoardSignal(name="power", pin=4, polarity=SignalPolarity.ACTIVE_HIGH),
            "reset": BoardSignal(name="reset", pin=5, polarity=SignalPolarity.ACTIVE_HIGH),
        },
        gp_aliases={"GP4": 4, "GP5": 5, "GP3": 3},
    )
    return HaloBoardWorkbench(bridge=bridge, config=config)
