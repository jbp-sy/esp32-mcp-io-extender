from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from esp32_mcp_io_extender.uart_pty import UartPtyManager, uart_pty_status


def test_status_reports_stale_pid(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "uart.alias"
    manager = UartPtyManager()
    sidecars = manager.sidecars(str(path))
    sidecars.pid.write_text("424242\n")
    sidecars.state.write_text(json.dumps({"path": str(path), "pid": 424242}))

    monkeypatch.setattr("esp32_mcp_io_extender.uart_pty.pid_is_running", lambda _pid: False)

    status = uart_pty_status(path=str(path))

    assert status["running"] is False
    assert status["stale"] is True
    assert status["pid"] == 424242


def test_start_rejects_if_running_pid_exists(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "uart.alias"
    manager = UartPtyManager()
    sidecars = manager.sidecars(str(path))
    sidecars.pid.write_text("123\n")
    sidecars.lock.write_text("123\n")

    monkeypatch.setattr("esp32_mcp_io_extender.uart_pty.pid_is_running", lambda _pid: True)

    with pytest.raises(RuntimeError):
        manager.start(path=str(path), name=None)


def test_stop_removes_alias_and_sidecars(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "uart.alias"
    path.write_text("")
    manager = UartPtyManager()
    sidecars = manager.sidecars(str(path))
    sidecars.pid.write_text(f"{os.getpid()}\n")
    sidecars.lock.write_text(f"{os.getpid()}\n")
    sidecars.state.write_text(json.dumps({"path": str(path), "pid": os.getpid()}))

    monkeypatch.setattr("esp32_mcp_io_extender.uart_pty.pid_is_running", lambda _pid: False)

    result = manager.stop(path=str(path))

    assert result["stopped"] is True
    assert not path.exists()
    assert not sidecars.pid.exists()
    assert not sidecars.lock.exists()
    assert not sidecars.state.exists()
