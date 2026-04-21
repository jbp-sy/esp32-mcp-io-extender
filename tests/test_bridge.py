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
