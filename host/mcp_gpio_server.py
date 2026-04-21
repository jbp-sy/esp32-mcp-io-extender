from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from esp_gpio_bridge import DeviceError, EspGpioBridge, GpioBridgeError, config_from_env


bridge = EspGpioBridge(config_from_env())
mcp = FastMCP("esp32-gpio")


def _call(cmd: str, **kwargs: Any) -> Any:
    try:
        return bridge.call(cmd, **kwargs)
    except DeviceError as exc:
        detail_msg = f" details={exc.details}" if exc.details else ""
        raise RuntimeError(f"firmware_error {exc.code}: {exc.message}{detail_msg}") from exc
    except GpioBridgeError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool
def gpio_ping() -> dict[str, Any]:
    """Check device connectivity and protocol metadata."""
    return bridge.request({"cmd": "ping"})


@mcp.tool
def gpio_info() -> dict[str, Any]:
    """Return firmware info and board safety policy (allowed/blocked pins)."""
    result = _call("info")
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_state() -> dict[str, Any]:
    """Return tracked runtime state for mode/digital/PWM and policy snapshot."""
    result = _call("state")
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_set_mode(pin: int, mode: str) -> dict[str, Any]:
    """Set GPIO mode. Modes: input, input_pullup, input_pulldown, output, output_open_drain."""
    result = _call("set_mode", pin=pin, mode=mode)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_write(pin: int, value: int) -> dict[str, Any]:
    """Write digital output value (0/1) on a policy-allowed output pin."""
    result = _call("write", pin=pin, value=1 if value else 0)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_read(pin: int) -> dict[str, Any]:
    """Read digital input value from a policy-allowed pin."""
    result = _call("read", pin=pin)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_adc_read(pin: int) -> dict[str, Any]:
    """Read raw ADC value from a policy-allowed ADC pin."""
    result = _call("adc_read", pin=pin)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_pwm_write(pin: int, value: int, freq: int = 5000, resolution: int = 8) -> dict[str, Any]:
    """Write PWM using LEDC on a policy-allowed pin."""
    result = _call("pwm_write", pin=pin, value=value, freq=freq, resolution=resolution)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_digital_write_pulse(pin: int, duration_ms: int = 100, pulse_value: int = 1, restore: int = 0) -> dict[str, Any]:
    """Pulse a digital output for duration_ms and restore to specified level."""
    result = _call(
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
    """Run a sequence of firmware ops in one request using the batch command."""
    response = bridge.request({"cmd": "batch", "ops": ops})
    if not response.get("ok", False):
        err = response.get("error") or {}
        raise RuntimeError(f"transaction_failed: {err}")
    result = response.get("result")
    assert isinstance(result, list)
    return {"count": len(result), "responses": result}


@mcp.tool
def gpio_serial_ports() -> list[dict[str, Any]]:
    """List candidate serial ports that look like USB MCU adapters."""
    out: list[dict[str, Any]] = []
    for p in EspGpioBridge.list_candidate_ports():
        out.append({"device": p.device, "description": p.description, "score": p.score})
    return out


@mcp.tool
def gpio_uart_info() -> dict[str, Any]:
    """Return UART bridge state and supported pins."""
    result = _call("uart_info")
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
    """Open UART bridge on reserved pins (default RX=20, TX=21)."""
    parity = (parity or "N").upper()[:1]
    result = _call(
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
    """Close UART bridge."""
    result = _call("uart_close")
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_uart_write_text(text: str, append_newline: bool = False, drain: bool = True) -> dict[str, Any]:
    """Write text bytes to UART."""
    result = _call("uart_write", text=text, append_newline=append_newline, drain=drain)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_uart_write_hex(hex_data: str, drain: bool = True) -> dict[str, Any]:
    """Write hex payload to UART (for example '55AA0D0A')."""
    result = _call("uart_write", hex=hex_data, drain=drain)
    assert isinstance(result, dict)
    return result


@mcp.tool
def gpio_uart_read(max_bytes: int = 128, timeout_ms: int = 20) -> dict[str, Any]:
    """Read bytes from UART, returning both ASCII preview and hex."""
    result = _call("uart_read", max_bytes=max_bytes, timeout_ms=timeout_ms)
    assert isinstance(result, dict)
    return result


if __name__ == "__main__":
    mcp.run()
