from __future__ import annotations

import pytest

import esp32_mcp_io_extender.cli as cli
from esp32_mcp_io_extender.bridge import CapabilitySnapshot, DetectedDevice


class _FakeBridge:
    devices = [
        DetectedDevice(device="/dev/cu.usbmodem1", description="ESP32 USB", score=9),
    ]
    calls: list[tuple[str, dict]] = []
    snapshots: list[CapabilitySnapshot] = [
        CapabilitySnapshot(policy={"pin_capabilities": {"4": {"digital_out": True, "digital_in": True}}})
    ]

    def __init__(self, config) -> None:
        self.config = config

    @classmethod
    def list_devices(cls, probe: bool = False):
        cls.calls.append(("list_devices", {"probe": probe}))
        return cls.devices

    def capabilities(self) -> CapabilitySnapshot:
        return self.snapshots[-1]

    def request(self, payload):
        self.calls.append(("request", payload))
        return {"ok": True, "result": {"pong": True}}

    def call(self, cmd: str, **kwargs):
        self.calls.append((cmd, kwargs))
        if cmd == "uart_info":
            return {
                "supported_rx_pin": 16,
                "supported_tx_pin": 17,
            }
        return {"cmd": cmd, **kwargs}

    def close(self) -> None:
        self.calls.append(("close", {}))


@pytest.fixture(autouse=True)
def fake_bridge(monkeypatch):
    _FakeBridge.calls = []
    _FakeBridge.devices = [
        DetectedDevice(device="/dev/cu.usbmodem1", description="ESP32 USB", score=9),
    ]
    _FakeBridge.snapshots = [
        CapabilitySnapshot(policy={"pin_capabilities": {"4": {"digital_out": True, "digital_in": True}}})
    ]
    monkeypatch.setattr(cli, "EspGpioBridge", _FakeBridge)


def test_parser_accepts_list_devices_without_subcommand() -> None:
    args = cli.build_parser().parse_args(["--list-devices", "--probe"])

    assert args.list_devices is True
    assert args.probe is True
    assert args.command is None


def test_main_lists_devices(capsys) -> None:
    code = cli.main(["--list-devices", "--probe"])

    assert code == 0
    assert ("list_devices", {"probe": True}) in _FakeBridge.calls
    assert "/dev/cu.usbmodem1" in capsys.readouterr().out


def test_main_probe_without_list_devices_filters_to_protocol_matches(capsys) -> None:
    _FakeBridge.devices = [
        DetectedDevice(device="/dev/cu.usbmodem1", description="ESP32 USB", score=9, is_protocol_device=True),
        DetectedDevice(device="/dev/cu.usbserial1", description="FTDI", score=6, is_protocol_device=False),
    ]

    code = cli.main(["--probe"])

    out = capsys.readouterr().out
    assert code == 0
    assert ("list_devices", {"probe": True}) in _FakeBridge.calls
    assert "/dev/cu.usbmodem1" in out
    assert "/dev/cu.usbserial1" not in out


def test_main_without_args_prints_help(capsys) -> None:
    code = cli.main([])

    captured = capsys.readouterr()
    assert code == 0
    assert "usage:" in captured.out
    assert "Discovery examples:" in captured.out
    assert captured.err == ""


def test_main_lists_capabilities(capsys) -> None:
    code = cli.main(["--port", "/dev/test", "--list-capabilities"])

    assert code == 0
    assert "pin_capabilities" in capsys.readouterr().out


def test_grouped_gpio_pulse_checks_capability_and_calls_bridge() -> None:
    code = cli.main(["--port", "/dev/test", "gpio", "pulse", "--pin", "4", "--state", "1", "--duration-ms", "100"])

    assert code == 0
    assert ("digital_write_pulse", {"pin": 4, "value": 1, "duration_ms": 100, "restore": 0}) in _FakeBridge.calls


def test_flat_gpio_duration_uses_pulse() -> None:
    code = cli.main(["--port", "/dev/test", "--gpio", "4", "--state", "1", "--duration-ms", "100"])

    assert code == 0
    mode_call = ("set_mode", {"pin": 4, "mode": "output"})
    pulse_call = ("digital_write_pulse", {"pin": 4, "value": 1, "duration_ms": 100, "restore": 0})
    assert mode_call in _FakeBridge.calls
    assert pulse_call in _FakeBridge.calls
    assert _FakeBridge.calls.index(mode_call) < _FakeBridge.calls.index(pulse_call)


def test_flat_gpio_without_duration_uses_write() -> None:
    code = cli.main(["--port", "/dev/test", "--gpio", "4", "--state", "1"])

    assert code == 0
    mode_call = ("set_mode", {"pin": 4, "mode": "output"})
    write_call = ("write", {"pin": 4, "value": 1})
    assert mode_call in _FakeBridge.calls
    assert write_call in _FakeBridge.calls
    assert _FakeBridge.calls.index(mode_call) < _FakeBridge.calls.index(write_call)


def test_grouped_uart_open_uses_uart_baud_without_changing_serial_baud() -> None:
    code = cli.main(["--port", "/dev/test", "uart", "open", "--baud", "9600"])

    assert code == 0
    assert ("uart_info", {}) in _FakeBridge.calls
    assert ("uart_open", {
        "baud": 9600,
        "rx_pin": 16,
        "tx_pin": 17,
        "data_bits": 8,
        "parity": "N",
        "stop_bits": 1,
        "timeout_ms": 20,
    }) in _FakeBridge.calls


def test_parser_rejects_uart_pty_start_without_path() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["uart", "pty", "start"])


def test_uart_pty_start_dispatches_to_helper(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_start(**kwargs):
        seen.update(kwargs)
        return {"running": True}

    monkeypatch.setattr(cli, "uart_pty_start", _fake_start)
    code = cli.main(
        [
            "--port",
            "/dev/test",
            "--baud",
            "115200",
            "--timeout",
            "3.0",
            "--retries",
            "1",
            "uart",
            "pty",
            "start",
            "--path",
            "/tmp/uart.esp32",
            "--name",
            "esp32",
            "--baud",
            "9600",
            "--timeout-ms",
            "50",
        ]
    )

    assert code == 0
    assert seen["path"] == "/tmp/uart.esp32"
    assert seen["name"] == "esp32"
    assert seen["uart_baud"] == 9600
    assert seen["timeout_ms"] == 50


def test_uart_pty_status_dispatches_to_helper(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_status(**kwargs):
        seen.update(kwargs)
        return {"running": False}

    monkeypatch.setattr(cli, "uart_pty_status", _fake_status)
    code = cli.main(["uart", "pty", "status", "--path", "/tmp/uart.esp32"])

    assert code == 0
    assert seen["path"] == "/tmp/uart.esp32"


def test_uart_pty_stop_dispatches_to_helper(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _fake_stop(**kwargs):
        seen.update(kwargs)
        return {"stopped": True}

    monkeypatch.setattr(cli, "uart_pty_stop", _fake_stop)
    code = cli.main(["uart", "pty", "stop", "--path", "/tmp/uart.esp32"])

    assert code == 0
    assert seen["path"] == "/tmp/uart.esp32"


def test_blocked_pin_fails_before_calling_write(capsys) -> None:
    _FakeBridge.snapshots = [
        CapabilitySnapshot(policy={"pin_capabilities": {"4": {"digital_out": False}}})
    ]

    code = cli.main(["--port", "/dev/test", "gpio", "write", "--pin", "4", "--state", "1"])

    assert code == 2
    assert ("write", {"pin": 4, "value": 1}) not in _FakeBridge.calls
    assert "does not offer digital_out" in capsys.readouterr().err
