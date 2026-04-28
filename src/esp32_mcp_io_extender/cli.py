from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .bridge import DetectedDevice, DeviceError, EspGpioBridge, SerialConfig, TransportError
from .uart_pty import uart_pty_start, uart_pty_status, uart_pty_stop


PIN_MODES = ["input", "input_pullup", "input_pulldown", "output", "output_open_drain"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ESP32 MCP IO serial CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Discovery examples:\n"
            "  esp32mcpio --list-devices\n"
            "  esp32mcpio --list-devices --probe\n"
            "  esp32mcpio --probe\n"
            "\n"
            "Notes:\n"
            "  --list-devices          Lists serial candidates from descriptor heuristics.\n"
            "  --list-devices --probe  Probes candidates and reports protocol=true/false.\n"
            "  --probe                 Probes and returns only protocol-compatible devices.\n"
            "  uart open/close/read/write controls firmware UART.\n"
            "  uart pty start/stop/status controls host-side PTY daemon lifecycle."
        ),
    )
    p.add_argument("--port", help="Serial port (default: auto-detect)")
    p.add_argument("--baud", dest="serial_baud", type=int, default=115200)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument(
        "--list-devices",
        action="store_true",
        help="List serial candidates (descriptor-heuristic based, no protocol handshake)",
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="Probe with ping/info; when used alone, prints only protocol-compatible devices",
    )
    p.add_argument("--list-capabilities", action="store_true", help="Print firmware capability policy for --port")

    p.add_argument("--gpio", type=int, help="Flat convenience GPIO pin selector (auto set-mode output)")
    p.add_argument("--state", type=int, choices=[0, 1], help="Flat convenience GPIO state")
    p.add_argument("--duration-ms", type=int, help="Flat convenience pulse duration")
    p.add_argument("--restore", type=int, default=0, choices=[0, 1], help="Flat convenience pulse restore state")

    sub = p.add_subparsers(dest="command")
    sub.add_parser("ping")
    sub.add_parser("info")
    sub.add_parser("state")

    s = sub.add_parser("set-mode")
    s.add_argument("pin", type=int)
    s.add_argument("mode", choices=PIN_MODES)

    w = sub.add_parser("write")
    w.add_argument("pin", type=int)
    w.add_argument("value", type=int, choices=[0, 1])

    r = sub.add_parser("read")
    r.add_argument("pin", type=int)

    a = sub.add_parser("adc")
    a.add_argument("pin", type=int)

    pwm = sub.add_parser("pwm")
    pwm.add_argument("pin", type=int)
    pwm.add_argument("value", type=int)
    pwm.add_argument("--freq", type=int, default=5000)
    pwm.add_argument("--resolution", type=int, default=8)

    pulse = sub.add_parser("pulse")
    pulse.add_argument("pin", type=int)
    pulse.add_argument("--duration-ms", type=int, default=100)
    pulse.add_argument("--pulse-value", type=int, default=1, choices=[0, 1])
    pulse.add_argument("--restore", type=int, default=0, choices=[0, 1])

    txn = sub.add_parser("batch")
    txn.add_argument("ops_json", help="JSON array of firmware ops")

    sub.add_parser("uart-info")

    uart_open = sub.add_parser("uart-open")
    uart_open.add_argument("--baud", dest="uart_baud", type=int, default=115200)
    uart_open.add_argument("--rx-pin", type=int)
    uart_open.add_argument("--tx-pin", type=int)
    uart_open.add_argument("--data-bits", type=int, default=8)
    uart_open.add_argument("--parity", choices=["N", "E", "O", "n", "e", "o"], default="N")
    uart_open.add_argument("--stop-bits", type=int, default=1)
    uart_open.add_argument("--timeout-ms", type=int, default=20)

    sub.add_parser("uart-close")

    uart_write_text = sub.add_parser("uart-write-text")
    uart_write_text.add_argument("text")
    uart_write_text.add_argument("--append-newline", action="store_true")
    uart_write_text.add_argument("--no-drain", action="store_true")

    uart_write_hex = sub.add_parser("uart-write-hex")
    uart_write_hex.add_argument("hex_data")
    uart_write_hex.add_argument("--no-drain", action="store_true")

    uart_read = sub.add_parser("uart-read")
    uart_read.add_argument("--max-bytes", type=int, default=128)
    uart_read.add_argument("--timeout-ms", type=int, default=20)

    gpio = sub.add_parser("gpio")
    gpio_sub = gpio.add_subparsers(dest="gpio_command", required=True)

    gpio_set_mode = gpio_sub.add_parser("set-mode")
    gpio_set_mode.add_argument("--pin", type=int, required=True)
    gpio_set_mode.add_argument("--mode", choices=PIN_MODES, required=True)

    gpio_write = gpio_sub.add_parser("write")
    gpio_write.add_argument("--pin", type=int, required=True)
    gpio_write.add_argument("--state", type=int, choices=[0, 1], required=True)

    gpio_pulse = gpio_sub.add_parser("pulse")
    gpio_pulse.add_argument("--pin", type=int, required=True)
    gpio_pulse.add_argument("--state", type=int, choices=[0, 1], required=True)
    gpio_pulse.add_argument("--duration-ms", type=int, default=100)
    gpio_pulse.add_argument("--restore", type=int, default=0, choices=[0, 1])

    gpio_read = gpio_sub.add_parser("read")
    gpio_read.add_argument("--pin", type=int, required=True)

    gpio_adc = gpio_sub.add_parser("adc")
    gpio_adc.add_argument("--pin", type=int, required=True)

    gpio_pwm = gpio_sub.add_parser("pwm")
    gpio_pwm.add_argument("--pin", type=int, required=True)
    gpio_pwm.add_argument("--value", type=int, required=True)
    gpio_pwm.add_argument("--freq", type=int, default=5000)
    gpio_pwm.add_argument("--resolution", type=int, default=8)

    uart = sub.add_parser("uart")
    uart_sub = uart.add_subparsers(dest="uart_command", required=True)
    uart_sub.add_parser("info")

    uart_open_grouped = uart_sub.add_parser("open")
    uart_open_grouped.add_argument("--baud", dest="uart_baud", type=int, default=115200)
    uart_open_grouped.add_argument("--rx-pin", type=int)
    uart_open_grouped.add_argument("--tx-pin", type=int)
    uart_open_grouped.add_argument("--data-bits", type=int, default=8)
    uart_open_grouped.add_argument("--parity", choices=["N", "E", "O", "n", "e", "o"], default="N")
    uart_open_grouped.add_argument("--stop-bits", type=int, default=1)
    uart_open_grouped.add_argument("--timeout-ms", type=int, default=20)

    uart_sub.add_parser("close")

    uart_write_text_grouped = uart_sub.add_parser("write-text")
    uart_write_text_grouped.add_argument("text")
    uart_write_text_grouped.add_argument("--append-newline", action="store_true")
    uart_write_text_grouped.add_argument("--no-drain", action="store_true")

    uart_write_hex_grouped = uart_sub.add_parser("write-hex")
    uart_write_hex_grouped.add_argument("hex_data")
    uart_write_hex_grouped.add_argument("--no-drain", action="store_true")

    uart_read_grouped = uart_sub.add_parser("read")
    uart_read_grouped.add_argument("--max-bytes", type=int, default=128)
    uart_read_grouped.add_argument("--timeout-ms", type=int, default=20)

    uart_pty = uart_sub.add_parser("pty")
    uart_pty_sub = uart_pty.add_subparsers(dest="uart_pty_command", required=True)

    uart_pty_start_cmd = uart_pty_sub.add_parser("start")
    uart_pty_start_cmd.add_argument("--path", required=True)
    uart_pty_start_cmd.add_argument("--name")
    uart_pty_start_cmd.add_argument("--baud", dest="uart_baud", type=int, default=115200)
    uart_pty_start_cmd.add_argument("--rx-pin", type=int)
    uart_pty_start_cmd.add_argument("--tx-pin", type=int)
    uart_pty_start_cmd.add_argument("--data-bits", type=int, default=8)
    uart_pty_start_cmd.add_argument("--parity", choices=["N", "E", "O", "n", "e", "o"], default="N")
    uart_pty_start_cmd.add_argument("--stop-bits", type=int, default=1)
    uart_pty_start_cmd.add_argument("--timeout-ms", type=int, default=20)

    uart_pty_stop_cmd = uart_pty_sub.add_parser("stop")
    uart_pty_stop_cmd.add_argument("--path", required=True)

    uart_pty_status_cmd = uart_pty_sub.add_parser("status")
    uart_pty_status_cmd.add_argument("--path", required=True)

    return p


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _device_to_dict(device: DetectedDevice) -> dict[str, Any]:
    data: dict[str, Any] = {
        "device": device.device,
        "description": device.description,
        "score": device.score,
        "protocol": device.is_protocol_device,
    }
    if device.info is not None:
        data["info"] = device.info
    if device.error:
        data["error"] = device.error
    return data


def _bridge_from_args(args: argparse.Namespace) -> EspGpioBridge:
    return EspGpioBridge(
        SerialConfig(
            port=args.port,
            baudrate=args.serial_baud,
            timeout=args.timeout,
            reconnect_retries=args.retries,
            auto_port=not bool(args.port),
        )
    )


def _capability_for_mode(mode: str) -> str:
    if mode.startswith("input"):
        return "digital_in"
    return "digital_out"


def _require_pin_capability(bridge: EspGpioBridge, pin: int, capability: str) -> None:
    snapshot = bridge.capabilities()
    if not snapshot.pin_supports(pin, capability):
        raise ValueError(f"pin {pin} does not offer {capability}")


def _run_gpio_command(bridge: EspGpioBridge, args: argparse.Namespace) -> Any:
    command = args.gpio_command
    if command == "set-mode":
        _require_pin_capability(bridge, args.pin, _capability_for_mode(args.mode))
        return bridge.call("set_mode", pin=args.pin, mode=args.mode)
    if command == "write":
        _require_pin_capability(bridge, args.pin, "digital_out")
        return bridge.call("write", pin=args.pin, value=args.state)
    if command == "pulse":
        _require_pin_capability(bridge, args.pin, "digital_out")
        return bridge.call(
            "digital_write_pulse",
            pin=args.pin,
            value=args.state,
            duration_ms=args.duration_ms,
            restore=args.restore,
        )
    if command == "read":
        _require_pin_capability(bridge, args.pin, "digital_in")
        return bridge.call("read", pin=args.pin)
    if command == "adc":
        _require_pin_capability(bridge, args.pin, "adc")
        return bridge.call("adc_read", pin=args.pin)
    if command == "pwm":
        _require_pin_capability(bridge, args.pin, "pwm")
        return bridge.call(
            "pwm_write",
            pin=args.pin,
            value=args.value,
            freq=args.freq,
            resolution=args.resolution,
        )
    raise ValueError(f"unknown gpio command: {command}")


def _run_uart_open(bridge: EspGpioBridge, args: argparse.Namespace) -> Any:
    rx_pin = args.rx_pin
    tx_pin = args.tx_pin
    if rx_pin is None or tx_pin is None:
        info = bridge.call("uart_info")
        if not isinstance(info, dict):
            raise ValueError("uart_info response was not an object")
        supported_rx = info.get("supported_rx_pin")
        supported_tx = info.get("supported_tx_pin")
        if not isinstance(supported_rx, int) or not isinstance(supported_tx, int):
            raise ValueError("uart_info response missing supported_rx_pin/supported_tx_pin")
        rx_pin = supported_rx
        tx_pin = supported_tx

    return bridge.call(
        "uart_open",
        baud=args.uart_baud,
        rx_pin=rx_pin,
        tx_pin=tx_pin,
        data_bits=args.data_bits,
        parity=args.parity.upper(),
        stop_bits=args.stop_bits,
        timeout_ms=args.timeout_ms,
    )


def _run_uart_command(bridge: EspGpioBridge, args: argparse.Namespace) -> Any:
    command = args.uart_command
    if command == "info":
        return bridge.call("uart_info")
    if command == "open":
        return _run_uart_open(bridge, args)
    if command == "close":
        return bridge.call("uart_close")
    if command == "write-text":
        return bridge.call("uart_write", text=args.text, append_newline=args.append_newline, drain=not args.no_drain)
    if command == "write-hex":
        return bridge.call("uart_write", hex=args.hex_data, drain=not args.no_drain)
    if command == "read":
        return bridge.call("uart_read", max_bytes=args.max_bytes, timeout_ms=args.timeout_ms)
    if command == "pty":
        pty_command = args.uart_pty_command
        if pty_command == "start":
            return uart_pty_start(
                path=args.path,
                name=args.name,
                port=args.port,
                serial_baud=args.serial_baud,
                serial_timeout=args.timeout,
                retries=args.retries,
                uart_baud=args.uart_baud,
                rx_pin=args.rx_pin,
                tx_pin=args.tx_pin,
                data_bits=args.data_bits,
                parity=args.parity.upper(),
                stop_bits=args.stop_bits,
                timeout_ms=args.timeout_ms,
            )
        if pty_command == "stop":
            return uart_pty_stop(path=args.path)
        if pty_command == "status":
            return uart_pty_status(path=args.path)
        raise ValueError(f"unknown uart pty command: {pty_command}")
    raise ValueError(f"unknown uart command: {command}")


def _run_flat_gpio(bridge: EspGpioBridge, args: argparse.Namespace) -> Any:
    if args.state is None:
        raise ValueError("--gpio requires --state")

    _require_pin_capability(bridge, args.gpio, "digital_out")
    bridge.call("set_mode", pin=args.gpio, mode="output")
    if args.duration_ms is not None:
        return bridge.call(
            "digital_write_pulse",
            pin=args.gpio,
            value=args.state,
            duration_ms=args.duration_ms,
            restore=args.restore,
        )
    return bridge.call("write", pin=args.gpio, value=args.state)


def _run_legacy_command(bridge: EspGpioBridge, args: argparse.Namespace) -> Any:
    if args.command == "ping":
        return bridge.request({"cmd": "ping"})
    if args.command == "info":
        return bridge.call("info")
    if args.command == "state":
        return bridge.call("state")
    if args.command == "set-mode":
        _require_pin_capability(bridge, args.pin, _capability_for_mode(args.mode))
        return bridge.call("set_mode", pin=args.pin, mode=args.mode)
    if args.command == "write":
        _require_pin_capability(bridge, args.pin, "digital_out")
        return bridge.call("write", pin=args.pin, value=args.value)
    if args.command == "read":
        _require_pin_capability(bridge, args.pin, "digital_in")
        return bridge.call("read", pin=args.pin)
    if args.command == "adc":
        _require_pin_capability(bridge, args.pin, "adc")
        return bridge.call("adc_read", pin=args.pin)
    if args.command == "pwm":
        _require_pin_capability(bridge, args.pin, "pwm")
        return bridge.call("pwm_write", pin=args.pin, value=args.value, freq=args.freq, resolution=args.resolution)
    if args.command == "pulse":
        _require_pin_capability(bridge, args.pin, "digital_out")
        return bridge.call(
            "digital_write_pulse",
            pin=args.pin,
            value=args.pulse_value,
            duration_ms=args.duration_ms,
            restore=args.restore,
        )
    if args.command == "batch":
        ops = json.loads(args.ops_json)
        if not isinstance(ops, list):
            raise ValueError("ops_json must decode to a list")
        return bridge.request({"cmd": "batch", "ops": ops})
    if args.command == "uart-info":
        return bridge.call("uart_info")
    if args.command == "uart-open":
        return _run_uart_open(bridge, args)
    if args.command == "uart-close":
        return bridge.call("uart_close")
    if args.command == "uart-write-text":
        return bridge.call("uart_write", text=args.text, append_newline=args.append_newline, drain=not args.no_drain)
    if args.command == "uart-write-hex":
        return bridge.call("uart_write", hex=args.hex_data, drain=not args.no_drain)
    if args.command == "uart-read":
        return bridge.call("uart_read", max_bytes=args.max_bytes, timeout_ms=args.timeout_ms)
    raise ValueError(f"unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if (
        args.command is None
        and args.gpio is None
        and not args.list_devices
        and not args.probe
        and not args.list_capabilities
    ):
        parser.print_help()
        return 0

    if args.list_devices or args.probe:
        devices = EspGpioBridge.list_devices(probe=args.probe)
        if args.probe and not args.list_devices:
            devices = [device for device in devices if device.is_protocol_device]
        print_json([_device_to_dict(device) for device in devices])
        return 0

    bridge: EspGpioBridge | None = None
    try:
        bridge = _bridge_from_args(args)

        if args.list_capabilities:
            print_json(bridge.capabilities().policy)
        elif args.gpio is not None:
            print_json(_run_flat_gpio(bridge, args))
        elif args.command == "gpio":
            print_json(_run_gpio_command(bridge, args))
        elif args.command == "uart":
            print_json(_run_uart_command(bridge, args))
        elif args.command is not None:
            print_json(_run_legacy_command(bridge, args))
        else:
            raise ValueError("command required unless --list-devices, --list-capabilities, or --gpio is used")

        return 0
    except (DeviceError, TransportError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if bridge is not None:
            bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
