from __future__ import annotations

import json
from pathlib import Path

import pytest

from esp32_mcp_io_extender.bridge import CapabilitySnapshot
from esp32_mcp_io_extender.named_endpoints import NamedGpioController, load_endpoint_config


class _FakeBridge:
    def __init__(self, policy: dict | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._snapshot = CapabilitySnapshot(
            policy=policy
            or {
                "pin_capabilities": {
                    "3": {"digital_in": True},
                    "4": {"digital_out": True},
                    "5": {"digital_out": True},
                    "6": {"adc": True},
                    "7": {"pwm": True},
                }
            }
        )

    def capabilities(self) -> CapabilitySnapshot:
        return self._snapshot

    def call(self, cmd: str, **kwargs):
        self.calls.append((cmd, kwargs))
        return {"cmd": cmd, **kwargs}


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_config() -> dict:
    return {
        "version": 1,
        "endpoints": [
            {
                "name": "reset",
                "pin": 4,
                "capabilities": ["digital_out"],
                "mode": "output",
                "active_value": 0,
                "inactive_value": 1,
                "description": "Active-low reset line",
                "tools": [
                    {
                        "name": "reset_pulse",
                        "operation": "pulse",
                        "duration_ms": 120,
                        "description": "Pulse reset low then restore high",
                    }
                ],
            },
            {
                "name": "button",
                "pin": 5,
                "capabilities": ["digital_out"],
                "active_value": 1,
                "inactive_value": 0,
                "tools": [{"name": "button_press", "operation": "pulse", "duration_ms": 120}],
            },
            {
                "name": "cap_status",
                "pin": 3,
                "capabilities": ["digital_in"],
                "mode": "input",
            },
            {
                "name": "adc_a0",
                "pin": 6,
                "capabilities": ["adc"],
            },
            {
                "name": "led_pwm",
                "pin": 7,
                "capabilities": ["pwm"],
                "mode": "output",
                "tools": [{"name": "led_pwm_write", "operation": "pwm_write"}],
            },
        ],
    }


def test_load_endpoint_config_accepts_valid_native_schema(tmp_path: Path) -> None:
    config = load_endpoint_config(_write_config(tmp_path, _valid_config()))

    assert config.version == 1
    assert config.resolve("RESET").pin == 4
    assert config.resolve("led_pwm").tools[0].name == "led_pwm_write"
    assert config.catalog()["endpoints"][0]["name"] == "reset"


def test_load_endpoint_config_rejects_duplicate_endpoint_names(tmp_path: Path) -> None:
    data = _valid_config()
    data["endpoints"].append({"name": "RESET", "pin": 6, "capabilities": ["adc"]})

    with pytest.raises(ValueError, match="duplicate endpoint name"):
        load_endpoint_config(_write_config(tmp_path, data))


def test_load_endpoint_config_rejects_invalid_or_colliding_dynamic_tool_names(tmp_path: Path) -> None:
    data = _valid_config()
    data["endpoints"][0]["tools"][0]["name"] = "gpio_named_write"

    with pytest.raises(ValueError, match="collides"):
        load_endpoint_config(_write_config(tmp_path, data))

    data = _valid_config()
    data["endpoints"][0]["tools"][0]["name"] = "bad-name"
    with pytest.raises(ValueError, match="invalid MCP tool name"):
        load_endpoint_config(_write_config(tmp_path, data))


def test_load_endpoint_config_rejects_tool_operation_capability_mismatch(tmp_path: Path) -> None:
    data = _valid_config()
    data["endpoints"][0]["tools"][0]["operation"] = "read"

    with pytest.raises(ValueError, match="requires capability digital_in"):
        load_endpoint_config(_write_config(tmp_path, data))


def test_named_controller_pulses_active_low_reset_with_config_defaults(tmp_path: Path) -> None:
    config = load_endpoint_config(_write_config(tmp_path, _valid_config()))
    bridge = _FakeBridge()
    controller = NamedGpioController(bridge, config)

    response = controller.pulse("reset")

    assert response["endpoint"]["name"] == "reset"
    assert bridge.calls == [
        ("set_mode", {"pin": 4, "mode": "output"}),
        ("digital_write_pulse", {"pin": 4, "value": 0, "duration_ms": 120, "restore": 1}),
    ]


def test_named_controller_write_preflights_before_mutation(tmp_path: Path) -> None:
    config = load_endpoint_config(_write_config(tmp_path, _valid_config()))
    bridge = _FakeBridge(policy={"pin_capabilities": {"5": {"digital_out": False}}})
    controller = NamedGpioController(bridge, config)

    with pytest.raises(ValueError, match="does not offer digital_out"):
        controller.write("button", 1)

    assert bridge.calls == []


def test_named_controller_read_adc_and_pwm_use_expected_modes_and_capabilities(tmp_path: Path) -> None:
    config = load_endpoint_config(_write_config(tmp_path, _valid_config()))
    bridge = _FakeBridge()
    controller = NamedGpioController(bridge, config)

    controller.read("cap_status")
    controller.adc_read("adc_a0")
    controller.pwm_write("led_pwm", 32)

    assert bridge.calls == [
        ("set_mode", {"pin": 3, "mode": "input"}),
        ("read", {"pin": 3}),
        ("adc_read", {"pin": 6}),
        ("set_mode", {"pin": 7, "mode": "output"}),
        ("pwm_write", {"pin": 7, "value": 32, "freq": 5000, "resolution": 8}),
    ]
