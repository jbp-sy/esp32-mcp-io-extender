from __future__ import annotations

import argparse
import os
from typing import Any

from .bridge import DeviceError, EspGpioBridge, GpioBridgeError
from .named_endpoints import GpioEndpoint, GpioEndpointConfig, NamedGpioController, load_endpoint_config


TOOL_SCOPES = frozenset({"raw", "named", "both"})


def run_mcp_server(
    bridge: EspGpioBridge,
    *,
    endpoint_config_path: str | None = None,
    tool_scope: str | None = None,
    endpoint_config: GpioEndpointConfig | None = None,
) -> int:
    # Keep FastMCP optional: only required when running MCP mode.
    from fastmcp import FastMCP

    mcp = FastMCP("esp32-gpio")
    scope = _normalize_tool_scope(tool_scope or os.environ.get("ESP_GPIO_MCP_TOOL_SCOPE") or "both")
    config = endpoint_config if endpoint_config is not None else _load_endpoint_config(endpoint_config_path)
    controller = NamedGpioController(bridge, config)

    def _call(cmd: str, **kwargs: Any) -> Any:
        try:
            return bridge.call(cmd, **kwargs)
        except DeviceError as exc:
            detail_msg = f" details={exc.details}" if exc.details else ""
            raise RuntimeError(f"firmware_error {exc.code}: {exc.message}{detail_msg}") from exc
        except GpioBridgeError as exc:
            raise RuntimeError(str(exc)) from exc

    if scope in {"raw", "both"}:
        _register_raw_tools(mcp, bridge, _call)

    if scope in {"named", "both"}:
        _register_named_tools(mcp, controller, config)

    mcp.run()
    return 0


def _register_raw_tools(mcp: Any, bridge: EspGpioBridge, call_fn: Any) -> None:
    @mcp.tool
    def gpio_ping() -> dict[str, Any]:
        return bridge.request({"cmd": "ping"})

    @mcp.tool
    def gpio_info() -> dict[str, Any]:
        result = call_fn("info")
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_state() -> dict[str, Any]:
        result = call_fn("state")
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_set_mode(pin: int, mode: str) -> dict[str, Any]:
        result = call_fn("set_mode", pin=pin, mode=mode)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_write(pin: int, value: int) -> dict[str, Any]:
        result = call_fn("write", pin=pin, value=1 if value else 0)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_read(pin: int) -> dict[str, Any]:
        result = call_fn("read", pin=pin)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_adc_read(pin: int) -> dict[str, Any]:
        result = call_fn("adc_read", pin=pin)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_pwm_write(pin: int, value: int, freq: int = 5000, resolution: int = 8) -> dict[str, Any]:
        result = call_fn("pwm_write", pin=pin, value=value, freq=freq, resolution=resolution)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_digital_write_pulse(pin: int, duration_ms: int = 100, pulse_value: int = 1, restore: int = 0) -> dict[str, Any]:
        result = call_fn(
            "digital_write_pulse",
            pin=pin,
            value=1 if pulse_value else 0,
            duration_ms=duration_ms,
            restore=1 if restore else 0,
        )
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_transaction(ops: list[dict[str, Any]]) -> dict[str, Any]:
        response = bridge.request({"cmd": "batch", "ops": ops})
        if not response.get("ok", False):
            err = response.get("error") or {}
            raise RuntimeError(f"transaction_failed: {err}")
        result = response.get("result")
        assert isinstance(result, list)
        return {"count": len(result), "responses": result}

    @mcp.tool
    def gpio_serial_ports() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in EspGpioBridge.list_candidate_ports():
            out.append({"device": p.device, "description": p.description, "score": p.score})
        return out

    @mcp.tool
    def gpio_uart_info() -> dict[str, Any]:
        result = call_fn("uart_info")
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_uart_open(
        baud: int = 115200,
        rx_pin: int = 20,
        tx_pin: int = 21,
        data_bits: int = 8,
        parity: str = "N",
        stop_bits: int = 1,
        timeout_ms: int = 20,
    ) -> dict[str, Any]:
        parity = (parity or "N").upper()[:1]
        result = call_fn(
            "uart_open",
            baud=baud,
            rx_pin=rx_pin,
            tx_pin=tx_pin,
            data_bits=data_bits,
            parity=parity,
            stop_bits=stop_bits,
            timeout_ms=timeout_ms,
        )
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_uart_close() -> dict[str, Any]:
        result = call_fn("uart_close")
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_uart_write_text(text: str, append_newline: bool = False, drain: bool = True) -> dict[str, Any]:
        result = call_fn("uart_write", text=text, append_newline=append_newline, drain=drain)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_uart_write_hex(hex_data: str, drain: bool = True) -> dict[str, Any]:
        result = call_fn("uart_write", hex=hex_data, drain=drain)
        assert isinstance(result, dict)
        return result

    @mcp.tool
    def gpio_uart_read(max_bytes: int = 128, timeout_ms: int = 20) -> dict[str, Any]:
        result = call_fn("uart_read", max_bytes=max_bytes, timeout_ms=timeout_ms)
        assert isinstance(result, dict)
        return result


def _register_named_tools(mcp: Any, controller: NamedGpioController, config: GpioEndpointConfig) -> None:
    @mcp.tool
    def gpio_named_endpoints() -> dict[str, Any]:
        return controller.endpoints()

    @mcp.tool
    def gpio_named_write(name: str, value: int) -> dict[str, Any]:
        return controller.write(name, value)

    @mcp.tool
    def gpio_named_read(name: str) -> dict[str, Any]:
        return controller.read(name)

    @mcp.tool
    def gpio_named_pulse(
        name: str,
        duration_ms: int | None = None,
        pulse_value: int | None = None,
        restore: int | None = None,
    ) -> dict[str, Any]:
        return controller.pulse(name, duration_ms=duration_ms, pulse_value=pulse_value, restore=restore)

    @mcp.tool
    def gpio_named_adc_read(name: str) -> dict[str, Any]:
        return controller.adc_read(name)

    @mcp.tool
    def gpio_named_pwm_write(name: str, value: int, freq: int = 5000, resolution: int = 8) -> dict[str, Any]:
        return controller.pwm_write(name, value, freq=freq, resolution=resolution)

    for endpoint in config.endpoints:
        for tool in endpoint.tools:
            dynamic = _make_dynamic_tool(controller, endpoint, tool.operation, tool.duration_ms)
            description = tool.description or f"{tool.operation} endpoint '{endpoint.name}' on GPIO{endpoint.pin}"
            mcp.tool(name=tool.name, description=description)(dynamic)


def _make_dynamic_tool(
    controller: NamedGpioController,
    endpoint: GpioEndpoint,
    operation: str,
    duration_ms_default: int | None,
) -> Any:
    endpoint_name = endpoint.name
    if operation == "write":
        def _write(value: int) -> dict[str, Any]:
            return controller.write(endpoint_name, value)

        return _write
    if operation == "read":
        def _read() -> dict[str, Any]:
            return controller.read(endpoint_name)

        return _read
    if operation == "pulse":
        def _pulse(
            duration_ms: int | None = None,
            pulse_value: int | None = None,
            restore: int | None = None,
        ) -> dict[str, Any]:
            duration = duration_ms if duration_ms is not None else duration_ms_default
            return controller.pulse(endpoint_name, duration_ms=duration, pulse_value=pulse_value, restore=restore)

        return _pulse
    if operation == "adc_read":
        def _adc_read() -> dict[str, Any]:
            return controller.adc_read(endpoint_name)

        return _adc_read
    if operation == "pwm_write":
        def _pwm_write(value: int, freq: int = 5000, resolution: int = 8) -> dict[str, Any]:
            return controller.pwm_write(endpoint_name, value, freq=freq, resolution=resolution)

        return _pwm_write
    raise ValueError(f"unsupported dynamic endpoint operation: {operation}")


def _load_endpoint_config(endpoint_config_path: str | None) -> GpioEndpointConfig:
    path = endpoint_config_path or os.environ.get("ESP_GPIO_ENDPOINT_CONFIG")
    if not path:
        return GpioEndpointConfig()
    return load_endpoint_config(path)


def _normalize_tool_scope(tool_scope: str) -> str:
    scope = tool_scope.strip().lower()
    if scope not in TOOL_SCOPES:
        raise ValueError(f"invalid MCP tool scope: {tool_scope}")
    return scope


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ESP32 GPIO MCP server")
    parser.add_argument("--endpoint-config", default=None, help="Native JSON named endpoint config path")
    parser.add_argument("--tool-scope", choices=sorted(TOOL_SCOPES), default=None, help="MCP tool surface to expose")
    return parser


def main(argv: list[str] | None = None) -> int:
    from .bridge import EspGpioBridge, config_from_env

    args = build_parser().parse_args(argv)
    bridge = EspGpioBridge(config_from_env())
    return run_mcp_server(bridge, endpoint_config_path=args.endpoint_config, tool_scope=args.tool_scope)


if __name__ == "__main__":
    raise SystemExit(main())
