from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import esp32_mcp_io_extender.mcp_server as mcp_server
from esp32_mcp_io_extender.bridge import CapabilitySnapshot


class _FakeFastMCP:
    instances: list["_FakeFastMCP"] = []

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, object] = {}
        _FakeFastMCP.instances.append(self)

    def tool(self, fn=None, **kwargs):
        def _register(func):
            self.tools[kwargs.get("name") or func.__name__] = func
            return func

        if fn is None:
            return _register
        return _register(fn)

    def run(self) -> None:
        return None


class _FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def capabilities(self) -> CapabilitySnapshot:
        return CapabilitySnapshot(
            policy={"pin_capabilities": {"4": {"digital_out": True}, "5": {"digital_out": True}, "7": {"pwm": True}}}
        )

    def request(self, payload):
        self.calls.append(("request", payload))
        return {"ok": True, "result": {"pong": True}, "meta": {}}

    def call(self, cmd: str, **kwargs):
        self.calls.append((cmd, kwargs))
        if cmd == "info":
            return {"policy": self.capabilities().policy}
        return {"cmd": cmd, **kwargs}


@pytest.fixture(autouse=True)
def fake_fastmcp(monkeypatch):
    _FakeFastMCP.instances = []
    monkeypatch.setitem(sys.modules, "fastmcp", SimpleNamespace(FastMCP=_FakeFastMCP))


def _config_path(tmp_path: Path) -> Path:
    path = tmp_path / "endpoints.json"
    path.write_text(
        json.dumps(
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
                        "tools": [{"name": "reset_pulse", "operation": "pulse", "duration_ms": 120}],
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
        ),
        encoding="utf-8",
    )
    return path


def test_mcp_raw_scope_registers_existing_raw_tools_only(tmp_path: Path) -> None:
    mcp_server.run_mcp_server(_FakeBridge(), endpoint_config_path=_config_path(tmp_path), tool_scope="raw")

    tools = _FakeFastMCP.instances[-1].tools
    assert "gpio_ping" in tools
    assert "gpio_named_endpoints" not in tools
    assert "reset_pulse" not in tools


def test_mcp_named_scope_registers_generic_and_configured_tools_only(tmp_path: Path) -> None:
    mcp_server.run_mcp_server(_FakeBridge(), endpoint_config_path=_config_path(tmp_path), tool_scope="named")

    tools = _FakeFastMCP.instances[-1].tools
    assert "gpio_ping" not in tools
    assert "gpio_named_endpoints" in tools
    assert "gpio_named_pulse" in tools
    assert "reset_pulse" in tools
    assert "led_pwm_write" in tools


def test_mcp_both_scope_registers_raw_named_and_dynamic_tools(tmp_path: Path) -> None:
    mcp_server.run_mcp_server(_FakeBridge(), endpoint_config_path=_config_path(tmp_path), tool_scope="both")

    tools = _FakeFastMCP.instances[-1].tools
    assert "gpio_ping" in tools
    assert "gpio_named_endpoints" in tools
    assert "reset_pulse" in tools


def test_mcp_dynamic_pulse_uses_named_controller_path(tmp_path: Path) -> None:
    bridge = _FakeBridge()
    mcp_server.run_mcp_server(bridge, endpoint_config_path=_config_path(tmp_path), tool_scope="named")

    result = _FakeFastMCP.instances[-1].tools["reset_pulse"]()

    assert result["endpoint"]["name"] == "reset"
    assert bridge.calls == [
        ("set_mode", {"pin": 4, "mode": "output"}),
        ("digital_write_pulse", {"pin": 4, "value": 0, "duration_ms": 120, "restore": 1}),
    ]
