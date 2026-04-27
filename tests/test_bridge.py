from __future__ import annotations

from types import SimpleNamespace

import pytest

import esp32_mcp_io_extender.bridge as bridge


class _FakeSerial:
    def __init__(self, *, lines: list[bytes]) -> None:
        self._lines = list(lines)
        self.is_open = True

    def write(self, data: bytes) -> int:
        return len(data)

    def flush(self) -> None:
        return

    def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        return b""

    def reset_input_buffer(self) -> None:
        return

    def reset_output_buffer(self) -> None:
        return

    def close(self) -> None:
        self.is_open = False


def test_list_candidate_ports_scores_and_sorts(monkeypatch) -> None:
    ports = [
        SimpleNamespace(device="/dev/cu.usbmodem123", description="ESP32 USB", hwid="USB VID:PID=303A:1001"),
        SimpleNamespace(device="/dev/cu.random", description="Bluetooth", hwid="n/a"),
    ]
    monkeypatch.setattr(bridge.list_ports, "comports", lambda: ports)

    result = bridge.EspGpioBridge.list_candidate_ports()

    assert len(result) == 1
    assert result[0].device == "/dev/cu.usbmodem123"


def test_request_ignores_boot_and_mismatched_ids(monkeypatch) -> None:
    fake_serial = _FakeSerial(
        lines=[
            b'{"event":"boot","ok":true}\n',
            b'{"ok":true,"id":"wrong","result":{}}\n',
            b'{"ok":true,"id":"fixed-id","result":{"pong":true}}\n',
        ]
    )
    monkeypatch.setattr(bridge.serial, "Serial", lambda *args, **kwargs: fake_serial)

    b = bridge.EspGpioBridge(bridge.SerialConfig(port="/dev/test", auto_port=False, timeout=0.2, boot_wait_s=0))
    response = b.request({"id": "fixed-id", "cmd": "ping"})

    assert response["ok"] is True
    assert response["result"]["pong"] is True


def test_call_maps_firmware_error_to_device_error(monkeypatch) -> None:
    b = bridge.EspGpioBridge(bridge.SerialConfig(port="/dev/test", auto_port=False))
    monkeypatch.setattr(
        b,
        "request",
        lambda _payload: {
            "ok": False,
            "error": {"code": "pin_blocked", "message": "blocked", "details": {"pin": 9}},
        },
    )

    with pytest.raises(bridge.DeviceError) as exc:
        b.call("write", pin=9, value=1)

    assert exc.value.code == "pin_blocked"
    assert exc.value.details == {"pin": 9}


def test_capability_snapshot_checks_pin_capability() -> None:
    snapshot = bridge.CapabilitySnapshot(
        policy={
            "pin_capabilities": {
                "4": {"digital_out": True, "digital_in": True},
                "20": {"digital_out": False},
            }
        }
    )

    assert snapshot.pin_supports(4, "digital_out") is True
    assert snapshot.pin_supports(20, "digital_out") is False
    assert snapshot.pin_supports(99, "digital_out") is False


def test_list_devices_passive_uses_candidate_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_candidate_ports",
        staticmethod(
            lambda: [
                bridge.PortCandidate(device="/dev/cu.usbmodem1", description="ESP32 USB", score=9),
                bridge.PortCandidate(device="/dev/cu.usbserial2", description="USB serial", score=4),
            ]
        ),
    )

    devices = bridge.EspGpioBridge.list_devices(probe=False)

    assert [item.device for item in devices] == ["/dev/cu.usbmodem1", "/dev/cu.usbserial2"]
    assert devices[0].is_protocol_device is False
    assert devices[0].info is None


def test_list_devices_probe_marks_protocol_devices(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_candidate_ports",
        staticmethod(lambda: [bridge.PortCandidate(device="/dev/cu.usbmodem1", description="ESP32 USB", score=9)]),
    )

    def fake_request(self, payload):
        assert payload == {"cmd": "ping"}
        return {"ok": True, "meta": {"protocol": bridge.PROTOCOL_NAME}}

    def fake_call(self, cmd, **kwargs):
        assert cmd == "info"
        assert kwargs == {}
        return {"board_id": "esp-rs-esp32-c3", "policy": {"allowed_pins": [4]}}

    monkeypatch.setattr(bridge.EspGpioBridge, "request", fake_request)
    monkeypatch.setattr(bridge.EspGpioBridge, "call", fake_call)
    monkeypatch.setattr(bridge.EspGpioBridge, "close", lambda self: None)

    devices = bridge.EspGpioBridge.list_devices(probe=True)

    assert len(devices) == 1
    assert devices[0].is_protocol_device is True
    assert devices[0].info == {"board_id": "esp-rs-esp32-c3", "policy": {"allowed_pins": [4]}}
    assert devices[0].error is None


def test_bridge_capabilities_wraps_info_policy(monkeypatch) -> None:
    b = bridge.EspGpioBridge(bridge.SerialConfig(port="/dev/test", auto_port=False))
    monkeypatch.setattr(
        b,
        "call",
        lambda cmd: {"policy": {"pin_capabilities": {"4": {"digital_out": True}}}},
    )

    snapshot = b.capabilities()

    assert snapshot.pin_supports(4, "digital_out") is True


def test_resolve_port_prefers_protocol_device_when_auto_port(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_devices",
        staticmethod(
            lambda probe=False: [
                bridge.DetectedDevice(device="/dev/cu.usbserial-ftdi", description="FTDI", score=8, is_protocol_device=False),
                bridge.DetectedDevice(device="/dev/cu.usbmodem-esp32", description="ESP32", score=6, is_protocol_device=True),
            ]
        ),
    )
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_candidate_ports",
        staticmethod(lambda: [bridge.PortCandidate(device="/dev/cu.usbserial-ftdi", description="FTDI", score=8)]),
    )

    b = bridge.EspGpioBridge(bridge.SerialConfig(auto_port=True))

    assert b._resolve_port() == "/dev/cu.usbmodem-esp32"


def test_resolve_port_falls_back_to_first_candidate_when_probe_finds_no_protocol(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_devices",
        staticmethod(
            lambda probe=False: [
                bridge.DetectedDevice(device="/dev/cu.usbserial-ftdi", description="FTDI", score=8, is_protocol_device=False),
            ]
        ),
    )
    monkeypatch.setattr(
        bridge.EspGpioBridge,
        "list_candidate_ports",
        staticmethod(
            lambda: [
                bridge.PortCandidate(device="/dev/cu.usbserial-ftdi", description="FTDI", score=8),
                bridge.PortCandidate(device="/dev/cu.usbmodem-other", description="Other", score=6),
            ]
        ),
    )

    b = bridge.EspGpioBridge(bridge.SerialConfig(auto_port=True))

    assert b._resolve_port() == "/dev/cu.usbserial-ftdi"
