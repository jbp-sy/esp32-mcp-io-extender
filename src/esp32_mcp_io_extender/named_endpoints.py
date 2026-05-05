from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bridge import CapabilitySnapshot, EspGpioBridge


ENDPOINT_OPERATIONS = frozenset({"write", "read", "pulse", "adc_read", "pwm_write"})
OPERATION_CAPABILITY = {
    "write": "digital_out",
    "read": "digital_in",
    "pulse": "digital_out",
    "adc_read": "adc",
    "pwm_write": "pwm",
}
PIN_MODES = frozenset({"input", "input_pullup", "input_pulldown", "output", "output_open_drain"})
MCP_TOOL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

BUILTIN_MCP_TOOL_NAMES = frozenset(
    {
        "gpio_ping",
        "gpio_info",
        "gpio_state",
        "gpio_set_mode",
        "gpio_write",
        "gpio_read",
        "gpio_adc_read",
        "gpio_pwm_write",
        "gpio_digital_write_pulse",
        "gpio_transaction",
        "gpio_serial_ports",
        "gpio_uart_info",
        "gpio_uart_open",
        "gpio_uart_close",
        "gpio_uart_write_text",
        "gpio_uart_write_hex",
        "gpio_uart_read",
        "gpio_named_endpoints",
        "gpio_named_write",
        "gpio_named_read",
        "gpio_named_pulse",
        "gpio_named_adc_read",
        "gpio_named_pwm_write",
    }
)


@dataclass(frozen=True, slots=True)
class GpioEndpointTool:
    name: str
    operation: str
    duration_ms: int | None = None
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GpioEndpointTool":
        name = _required_str(raw, "name")
        operation = _required_str(raw, "operation")
        duration_raw = raw.get("duration_ms")
        return cls(
            name=name,
            operation=operation,
            duration_ms=int(duration_raw) if duration_raw is not None else None,
            description=str(raw.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "operation": self.operation,
        }
        if self.duration_ms is not None:
            out["duration_ms"] = self.duration_ms
        if self.description:
            out["description"] = self.description
        return out


@dataclass(frozen=True, slots=True)
class GpioEndpoint:
    name: str
    pin: int
    capabilities: tuple[str, ...]
    mode: str | None = None
    active_value: int = 1
    inactive_value: int = 0
    description: str = ""
    tools: tuple[GpioEndpointTool, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GpioEndpoint":
        name = _required_str(raw, "name")
        pin = int(raw["pin"])
        capabilities_raw = raw.get("capabilities", [])
        if not isinstance(capabilities_raw, list):
            raise ValueError(f"endpoint '{name}' capabilities must be an array")
        tools_raw = raw.get("tools", [])
        if not isinstance(tools_raw, list):
            raise ValueError(f"endpoint '{name}' tools must be an array")

        mode_raw = raw.get("mode")
        mode = str(mode_raw) if mode_raw is not None else None
        return cls(
            name=name,
            pin=pin,
            capabilities=tuple(str(item) for item in capabilities_raw),
            mode=mode,
            active_value=_digital_value(raw.get("active_value", 1), field_name=f"{name}.active_value"),
            inactive_value=_digital_value(raw.get("inactive_value", 0), field_name=f"{name}.inactive_value"),
            description=str(raw.get("description", "")),
            tools=tuple(GpioEndpointTool.from_dict(tool) for tool in tools_raw),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "pin": self.pin,
            "capabilities": list(self.capabilities),
            "active_value": self.active_value,
            "inactive_value": self.inactive_value,
        }
        if self.mode is not None:
            out["mode"] = self.mode
        if self.description:
            out["description"] = self.description
        if self.tools:
            out["tools"] = [tool.to_dict() for tool in self.tools]
        return out


@dataclass(frozen=True, slots=True)
class GpioEndpointConfig:
    endpoints: tuple[GpioEndpoint, ...] = field(default_factory=tuple)
    version: int = 1

    def __post_init__(self) -> None:
        _validate_config(self)

    def resolve(self, name: str) -> GpioEndpoint:
        key = _endpoint_key(name)
        for endpoint in self.endpoints:
            if _endpoint_key(endpoint.name) == key:
                return endpoint
        raise KeyError(f"unknown endpoint: {name}")

    def catalog(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "endpoints": [endpoint.to_dict() for endpoint in self.endpoints],
        }


class NamedGpioController:
    def __init__(self, bridge: EspGpioBridge, config: GpioEndpointConfig):
        self.bridge = bridge
        self.config = config

    def endpoints(self) -> dict[str, Any]:
        return self.config.catalog()

    def write(self, name: str, value: int) -> dict[str, Any]:
        endpoint = self.config.resolve(name)
        self._require_capability(endpoint, "digital_out")
        self._set_mode(endpoint, "output")
        result = self.bridge.call("write", pin=endpoint.pin, value=1 if value else 0)
        return self._wrap(endpoint, result)

    def read(self, name: str) -> dict[str, Any]:
        endpoint = self.config.resolve(name)
        self._require_capability(endpoint, "digital_in")
        self._set_mode(endpoint, "input")
        result = self.bridge.call("read", pin=endpoint.pin)
        return self._wrap(endpoint, result)

    def pulse(
        self,
        name: str,
        *,
        duration_ms: int | None = None,
        pulse_value: int | None = None,
        restore: int | None = None,
    ) -> dict[str, Any]:
        endpoint = self.config.resolve(name)
        tool_default = self._first_tool_default(endpoint, "pulse")
        duration = int(duration_ms if duration_ms is not None else tool_default or 100)
        value = _digital_value(
            endpoint.active_value if pulse_value is None else pulse_value,
            field_name="pulse_value",
        )
        restore_value = _digital_value(
            endpoint.inactive_value if restore is None else restore,
            field_name="restore",
        )
        self._require_capability(endpoint, "digital_out")
        self._set_mode(endpoint, "output")
        result = self.bridge.call(
            "digital_write_pulse",
            pin=endpoint.pin,
            value=value,
            duration_ms=duration,
            restore=restore_value,
        )
        return self._wrap(endpoint, result)

    def adc_read(self, name: str) -> dict[str, Any]:
        endpoint = self.config.resolve(name)
        self._require_capability(endpoint, "adc")
        if endpoint.mode is not None:
            self.bridge.call("set_mode", pin=endpoint.pin, mode=endpoint.mode)
        result = self.bridge.call("adc_read", pin=endpoint.pin)
        return self._wrap(endpoint, result)

    def pwm_write(self, name: str, value: int, *, freq: int = 5000, resolution: int = 8) -> dict[str, Any]:
        endpoint = self.config.resolve(name)
        self._require_capability(endpoint, "pwm")
        self._set_mode(endpoint, "output")
        result = self.bridge.call(
            "pwm_write",
            pin=endpoint.pin,
            value=value,
            freq=freq,
            resolution=resolution,
        )
        return self._wrap(endpoint, result)

    def _set_mode(self, endpoint: GpioEndpoint, fallback: str) -> None:
        self.bridge.call("set_mode", pin=endpoint.pin, mode=endpoint.mode or fallback)

    def _require_capability(self, endpoint: GpioEndpoint, capability: str) -> None:
        snapshot = self.bridge.capabilities()
        if not _snapshot_supports(snapshot, endpoint.pin, capability):
            raise ValueError(f"endpoint '{endpoint.name}' pin {endpoint.pin} does not offer {capability}")

    @staticmethod
    def _first_tool_default(endpoint: GpioEndpoint, operation: str) -> int | None:
        for tool in endpoint.tools:
            if tool.operation == operation and tool.duration_ms is not None:
                return tool.duration_ms
        return None

    @staticmethod
    def _wrap(endpoint: GpioEndpoint, result: Any) -> dict[str, Any]:
        return {
            "endpoint": {
                "name": endpoint.name,
                "pin": endpoint.pin,
                "capabilities": list(endpoint.capabilities),
            },
            "result": result,
        }


def load_endpoint_config(path: str | Path) -> GpioEndpointConfig:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("endpoint config must be a JSON object")
    version = int(raw.get("version", 1))
    endpoints_raw = raw.get("endpoints", [])
    if not isinstance(endpoints_raw, list):
        raise ValueError("endpoint config endpoints must be an array")
    endpoints = tuple(GpioEndpoint.from_dict(item) for item in endpoints_raw)
    return GpioEndpointConfig(version=version, endpoints=endpoints)


def _validate_config(config: GpioEndpointConfig) -> None:
    if config.version != 1:
        raise ValueError(f"unsupported endpoint config version: {config.version}")

    endpoint_names: set[str] = set()
    tool_names: set[str] = set()
    for endpoint in config.endpoints:
        key = _endpoint_key(endpoint.name)
        if key in endpoint_names:
            raise ValueError(f"duplicate endpoint name: {endpoint.name}")
        endpoint_names.add(key)

        if endpoint.mode is not None and endpoint.mode not in PIN_MODES:
            raise ValueError(f"endpoint '{endpoint.name}' has invalid mode: {endpoint.mode}")

        for capability in endpoint.capabilities:
            if capability not in set(OPERATION_CAPABILITY.values()):
                raise ValueError(f"endpoint '{endpoint.name}' has invalid capability: {capability}")

        caps = set(endpoint.capabilities)
        for tool in endpoint.tools:
            if not MCP_TOOL_NAME_RE.match(tool.name):
                raise ValueError(f"invalid MCP tool name: {tool.name}")
            if tool.name in BUILTIN_MCP_TOOL_NAMES or tool.name in tool_names:
                raise ValueError(f"MCP tool name '{tool.name}' collides with another tool")
            tool_names.add(tool.name)

            if tool.operation not in ENDPOINT_OPERATIONS:
                raise ValueError(f"endpoint '{endpoint.name}' has invalid tool operation: {tool.operation}")
            required = OPERATION_CAPABILITY[tool.operation]
            if required not in caps:
                raise ValueError(f"endpoint '{endpoint.name}' tool '{tool.name}' requires capability {required}")


def _required_str(raw: dict[str, Any], field_name: str) -> str:
    value = str(raw.get(field_name, "")).strip()
    if not value:
        raise ValueError(f"missing required field: {field_name}")
    return value


def _endpoint_key(name: str) -> str:
    return name.strip().lower()


def _digital_value(value: Any, *, field_name: str) -> int:
    out = int(value)
    if out not in {0, 1}:
        raise ValueError(f"{field_name} must be 0 or 1")
    return out


def _snapshot_supports(snapshot: CapabilitySnapshot, pin: int, capability: str) -> bool:
    return snapshot.pin_supports(pin, capability)
