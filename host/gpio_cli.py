from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from esp_gpio_bridge import DeviceError, EspGpioBridge, SerialConfig, TransportError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ESP32 GPIO serial CLI tester")
    p.add_argument("--port", help="Serial port (default: auto-detect)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--retries", type=int, default=2)

    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("ping")
    sub.add_parser("info")
    sub.add_parser("state")

    s = sub.add_parser("set-mode")
    s.add_argument("pin", type=int)
    s.add_argument("mode", choices=["input", "input_pullup", "input_pulldown", "output", "output_open_drain"])

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

    uart_info = sub.add_parser("uart-info")

    uart_open = sub.add_parser("uart-open")
    uart_open.add_argument("--baud", type=int, default=115200)
    uart_open.add_argument("--rx-pin", type=int, default=20)
    uart_open.add_argument("--tx-pin", type=int, default=21)
    uart_open.add_argument("--data-bits", type=int, default=8)
    uart_open.add_argument("--parity", choices=["N", "E", "O", "n", "e", "o"], default="N")
    uart_open.add_argument("--stop-bits", type=int, default=1)
    uart_open.add_argument("--timeout-ms", type=int, default=20)

    uart_close = sub.add_parser("uart-close")

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

    return p


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> int:
    args = build_parser().parse_args()
    config = SerialConfig(
        port=args.port,
        baudrate=args.baud,
        timeout=args.timeout,
        reconnect_retries=args.retries,
        auto_port=not bool(args.port),
    )
    bridge = EspGpioBridge(config)

    try:
        if args.command == "ping":
            print_json(bridge.request({"cmd": "ping"}))
        elif args.command == "info":
            print_json(bridge.call("info"))
        elif args.command == "state":
            print_json(bridge.call("state"))
        elif args.command == "set-mode":
            print_json(bridge.call("set_mode", pin=args.pin, mode=args.mode))
        elif args.command == "write":
            print_json(bridge.call("write", pin=args.pin, value=args.value))
        elif args.command == "read":
            print_json(bridge.call("read", pin=args.pin))
        elif args.command == "adc":
            print_json(bridge.call("adc_read", pin=args.pin))
        elif args.command == "pwm":
            print_json(
                bridge.call(
                    "pwm_write",
                    pin=args.pin,
                    value=args.value,
                    freq=args.freq,
                    resolution=args.resolution,
                )
            )
        elif args.command == "pulse":
            print_json(
                bridge.call(
                    "digital_write_pulse",
                    pin=args.pin,
                    value=args.pulse_value,
                    duration_ms=args.duration_ms,
                    restore=args.restore,
                )
            )
        elif args.command == "batch":
            ops = json.loads(args.ops_json)
            if not isinstance(ops, list):
                raise ValueError("ops_json must decode to a list")
            print_json(bridge.request({"cmd": "batch", "ops": ops}))
        elif args.command == "uart-info":
            print_json(bridge.call("uart_info"))
        elif args.command == "uart-open":
            print_json(
                bridge.call(
                    "uart_open",
                    baud=args.baud,
                    rx_pin=args.rx_pin,
                    tx_pin=args.tx_pin,
                    data_bits=args.data_bits,
                    parity=args.parity.upper(),
                    stop_bits=args.stop_bits,
                    timeout_ms=args.timeout_ms,
                )
            )
        elif args.command == "uart-close":
            print_json(bridge.call("uart_close"))
        elif args.command == "uart-write-text":
            print_json(
                bridge.call(
                    "uart_write",
                    text=args.text,
                    append_newline=args.append_newline,
                    drain=not args.no_drain,
                )
            )
        elif args.command == "uart-write-hex":
            print_json(bridge.call("uart_write", hex=args.hex_data, drain=not args.no_drain))
        elif args.command == "uart-read":
            print_json(bridge.call("uart_read", max_bytes=args.max_bytes, timeout_ms=args.timeout_ms))
        else:
            raise ValueError(f"unknown command: {args.command}")

        return 0
    except (DeviceError, TransportError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
