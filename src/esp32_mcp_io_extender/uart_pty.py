from __future__ import annotations

import argparse
import errno
import json
import os
import pty
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bridge import DeviceError, EspGpioBridge, SerialConfig, TransportError


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(slots=True)
class SidecarPaths:
    alias: Path
    pid: Path
    state: Path
    lock: Path


class UartPtyManager:
    def sidecars(self, path: str) -> SidecarPaths:
        alias = Path(path)
        return SidecarPaths(
            alias=alias,
            pid=Path(f"{path}.esp32mcpio.pid"),
            state=Path(f"{path}.esp32mcpio.state.json"),
            lock=Path(f"{path}.esp32mcpio.lock"),
        )

    def status(self, path: str) -> dict[str, Any]:
        sidecars = self.sidecars(path)
        pid = self._read_pid(sidecars.pid)
        running = bool(pid and pid_is_running(pid))
        stale = bool(pid and not running)
        state_data = self._read_state(sidecars.state)

        result: dict[str, Any] = {
            "path": path,
            "pid": pid,
            "running": running,
            "stale": stale,
            "state_file": str(sidecars.state),
            "pid_file": str(sidecars.pid),
            "lock_file": str(sidecars.lock),
            "alias_exists": os.path.lexists(sidecars.alias),
        }
        if isinstance(state_data, dict):
            result.update(state_data)
        return result

    def start(
        self,
        *,
        path: str,
        name: str | None = None,
        port: str | None = None,
        serial_baud: int = 115200,
        serial_timeout: float = 2.0,
        retries: int = 2,
        uart_baud: int = 115200,
        rx_pin: int | None = None,
        tx_pin: int | None = None,
        data_bits: int = 8,
        parity: str = "N",
        stop_bits: int = 1,
        timeout_ms: int = 20,
        startup_timeout_s: float = 6.0,
    ) -> dict[str, Any]:
        if not path:
            raise ValueError("path is required")

        sidecars = self.sidecars(path)
        current = self.status(path)
        if current["running"]:
            raise RuntimeError(f"uart pty daemon already running for path={path}")
        if current["stale"]:
            self._cleanup_sidecars(sidecars, remove_alias=True)

        sidecars.alias.parent.mkdir(parents=True, exist_ok=True)
        sidecars.lock.parent.mkdir(parents=True, exist_ok=True)

        if sidecars.lock.exists():
            lock_pid = self._read_pid(sidecars.lock)
            if lock_pid and pid_is_running(lock_pid):
                raise RuntimeError(f"uart pty lock is active for path={path}")
            sidecars.lock.unlink(missing_ok=True)

        sidecars.lock.write_text(f"{os.getpid()}\n")

        cmd = [sys.executable, "-m", "esp32_mcp_io_extender.uart_pty", "daemon", "--path", path]
        if name:
            cmd.extend(["--name", name])
        if port:
            cmd.extend(["--port", port])
        cmd.extend(["--serial-baud", str(serial_baud)])
        cmd.extend(["--serial-timeout", str(serial_timeout)])
        cmd.extend(["--retries", str(retries)])
        cmd.extend(["--uart-baud", str(uart_baud)])
        if rx_pin is not None:
            cmd.extend(["--rx-pin", str(rx_pin)])
        if tx_pin is not None:
            cmd.extend(["--tx-pin", str(tx_pin)])
        cmd.extend(["--data-bits", str(data_bits)])
        cmd.extend(["--parity", parity.upper()])
        cmd.extend(["--stop-bits", str(stop_bits)])
        cmd.extend(["--timeout-ms", str(timeout_ms)])

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

        deadline = time.monotonic() + startup_timeout_s
        while time.monotonic() < deadline:
            status = self.status(path)
            if status["running"]:
                return status
            if proc.poll() is not None:
                break
            time.sleep(0.1)

        self._cleanup_sidecars(sidecars, remove_alias=True)
        raise RuntimeError(f"uart pty daemon failed to start for path={path}")

    def stop(self, *, path: str, timeout_s: float = 5.0) -> dict[str, Any]:
        sidecars = self.sidecars(path)
        before = self.status(path)
        pid = before.get("pid")
        was_running = bool(before.get("running"))

        if isinstance(pid, int) and pid > 0 and pid_is_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline and pid_is_running(pid):
                time.sleep(0.1)

            if pid_is_running(pid):
                os.kill(pid, signal.SIGKILL)

        self._cleanup_sidecars(sidecars, remove_alias=True)
        return {
            "path": path,
            "pid": pid,
            "was_running": was_running,
            "stopped": True,
        }

    def _read_pid(self, path: Path) -> int | None:
        if not path.exists():
            return None
        text = path.read_text().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _read_state(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _cleanup_sidecars(self, sidecars: SidecarPaths, *, remove_alias: bool) -> None:
        if remove_alias and os.path.lexists(sidecars.alias):
            sidecars.alias.unlink(missing_ok=True)
        sidecars.pid.unlink(missing_ok=True)
        sidecars.state.unlink(missing_ok=True)
        sidecars.lock.unlink(missing_ok=True)


def _resolve_uart_pins(bridge: EspGpioBridge, rx_pin: int | None, tx_pin: int | None) -> tuple[int, int]:
    if rx_pin is not None and tx_pin is not None:
        return rx_pin, tx_pin

    info = bridge.call("uart_info")
    if not isinstance(info, dict):
        raise RuntimeError("uart_info did not return an object")

    supported_rx = info.get("supported_rx_pin")
    supported_tx = info.get("supported_tx_pin")
    if not isinstance(supported_rx, int) or not isinstance(supported_tx, int):
        raise RuntimeError("uart_info missing supported_rx_pin/supported_tx_pin")
    return supported_rx, supported_tx


def run_uart_pty_daemon(
    *,
    path: str,
    name: str | None = None,
    port: str | None = None,
    serial_baud: int = 115200,
    serial_timeout: float = 2.0,
    retries: int = 2,
    uart_baud: int = 115200,
    rx_pin: int | None = None,
    tx_pin: int | None = None,
    data_bits: int = 8,
    parity: str = "N",
    stop_bits: int = 1,
    timeout_ms: int = 20,
) -> int:
    manager = UartPtyManager()
    sidecars = manager.sidecars(path)
    sidecars.alias.parent.mkdir(parents=True, exist_ok=True)
    sidecars.lock.parent.mkdir(parents=True, exist_ok=True)

    should_stop = False

    def _handle_stop(_signum: int, _frame: Any) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    serial_cfg = SerialConfig(
        port=port,
        baudrate=serial_baud,
        timeout=serial_timeout,
        reconnect_retries=retries,
        auto_port=not bool(port),
    )
    bridge = EspGpioBridge(serial_cfg)

    master_fd = -1
    try:
        sidecars.pid.write_text(f"{os.getpid()}\n")
        sidecars.lock.write_text(f"{os.getpid()}\n")

        resolved_rx, resolved_tx = _resolve_uart_pins(bridge, rx_pin, tx_pin)
        bridge.call(
            "uart_open",
            baud=uart_baud,
            rx_pin=resolved_rx,
            tx_pin=resolved_tx,
            data_bits=data_bits,
            parity=parity.upper(),
            stop_bits=stop_bits,
            timeout_ms=timeout_ms,
        )

        master_fd, slave_fd = pty.openpty()
        slave_name = os.ttyname(slave_fd)
        os.close(slave_fd)
        if os.path.lexists(sidecars.alias):
            sidecars.alias.unlink(missing_ok=True)
        os.symlink(slave_name, sidecars.alias)

        state = {
            "path": path,
            "name": name,
            "pid": os.getpid(),
            "serial_port": bridge.active_port,
            "pty_slave": slave_name,
            "uart_baud": uart_baud,
            "rx_pin": resolved_rx,
            "tx_pin": resolved_tx,
            "data_bits": data_bits,
            "parity": parity.upper(),
            "stop_bits": stop_bits,
            "timeout_ms": timeout_ms,
        }
        sidecars.state.write_text(json.dumps(state, indent=2, sort_keys=True))

        while not should_stop:
            readable, _, _ = select.select([master_fd], [], [], 0.02)
            if readable:
                try:
                    outbound = os.read(master_fd, 512)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        outbound = b""
                    else:
                        raise
                if outbound:
                    bridge.call("uart_write", hex=outbound.hex().upper(), drain=True)

            inbound = bridge.call("uart_read", max_bytes=256, timeout_ms=20)
            if isinstance(inbound, dict):
                hex_data = inbound.get("hex")
                if isinstance(hex_data, str) and hex_data:
                    try:
                        os.write(master_fd, bytes.fromhex(hex_data))
                    except ValueError:
                        # Ignore malformed hex from device preview conversion edge cases.
                        pass
        return 0
    except (DeviceError, TransportError, RuntimeError, OSError):
        return 2
    finally:
        try:
            bridge.call("uart_close")
        except Exception:
            pass
        bridge.close()
        if master_fd >= 0:
            os.close(master_fd)

        if os.path.lexists(sidecars.alias):
            sidecars.alias.unlink(missing_ok=True)
        sidecars.pid.unlink(missing_ok=True)
        sidecars.state.unlink(missing_ok=True)
        sidecars.lock.unlink(missing_ok=True)


def uart_pty_start(**kwargs: Any) -> dict[str, Any]:
    return UartPtyManager().start(**kwargs)


def uart_pty_stop(**kwargs: Any) -> dict[str, Any]:
    return UartPtyManager().stop(**kwargs)


def uart_pty_status(**kwargs: Any) -> dict[str, Any]:
    return UartPtyManager().status(**kwargs)


def _build_daemon_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Internal UART PTY daemon entrypoint")
    sub = p.add_subparsers(dest="cmd", required=True)
    daemon = sub.add_parser("daemon")
    daemon.add_argument("--path", required=True)
    daemon.add_argument("--name")
    daemon.add_argument("--port")
    daemon.add_argument("--serial-baud", type=int, default=115200)
    daemon.add_argument("--serial-timeout", type=float, default=2.0)
    daemon.add_argument("--retries", type=int, default=2)
    daemon.add_argument("--uart-baud", type=int, default=115200)
    daemon.add_argument("--rx-pin", type=int)
    daemon.add_argument("--tx-pin", type=int)
    daemon.add_argument("--data-bits", type=int, default=8)
    daemon.add_argument("--parity", choices=["N", "E", "O", "n", "e", "o"], default="N")
    daemon.add_argument("--stop-bits", type=int, default=1)
    daemon.add_argument("--timeout-ms", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_daemon_parser().parse_args(argv)
    if args.cmd != "daemon":
        return 2
    return run_uart_pty_daemon(
        path=args.path,
        name=args.name,
        port=args.port,
        serial_baud=args.serial_baud,
        serial_timeout=args.serial_timeout,
        retries=args.retries,
        uart_baud=args.uart_baud,
        rx_pin=args.rx_pin,
        tx_pin=args.tx_pin,
        data_bits=args.data_bits,
        parity=args.parity.upper(),
        stop_bits=args.stop_bits,
        timeout_ms=args.timeout_ms,
    )


if __name__ == "__main__":
    raise SystemExit(main())
