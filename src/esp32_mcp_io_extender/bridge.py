from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import serial
from serial.tools import list_ports


PROTOCOL_NAME = "esp32-gpio-jsonl"


class GpioBridgeError(RuntimeError):
    """Base host-side GPIO bridge error."""


class DeviceError(GpioBridgeError):
    """Raised when firmware returns ok=false."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None, raw: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        self.raw = raw or {}
        super().__init__(f"device_error[{code}]: {message}")


class TransportError(GpioBridgeError):
    """Raised when serial transport cannot complete a request."""


@dataclass(slots=True)
class SerialConfig:
    port: str | None = None
    baudrate: int = 115200
    timeout: float = 2.0
    boot_wait_s: float = 0.8
    reconnect_retries: int = 2
    reconnect_backoff_s: float = 0.25
    auto_port: bool = True


@dataclass(slots=True)
class PortCandidate:
    device: str
    description: str
    score: int


class EspGpioBridge:
    def __init__(self, config: SerialConfig):
        self.config = config
        self._lock = threading.Lock()
        self._serial: serial.Serial | None = None
        self._active_port: str | None = None

    @staticmethod
    def list_candidate_ports() -> list[PortCandidate]:
        candidates: list[PortCandidate] = []
        for p in list_ports.comports():
            score = 0
            dev = (p.device or "").lower()
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()

            if any(token in dev for token in ("usbmodem", "ttyacm", "usbserial", "tty.usb")):
                score += 4
            if any(token in desc for token in ("esp32", "esp", "cp210", "ch340", "usb serial")):
                score += 3
            if any(token in hwid for token in ("303a", "10c4", "1a86", "0403")):
                score += 2

            if score > 0:
                candidates.append(PortCandidate(device=p.device, description=p.description or "", score=score))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _resolve_port(self) -> str:
        if self.config.port:
            return self.config.port

        if not self.config.auto_port:
            raise TransportError("serial port is required (set ESP_GPIO_PORT)")

        candidates = self.list_candidate_ports()
        if not candidates:
            raise TransportError("no candidate serial ports found; set ESP_GPIO_PORT explicitly")
        return candidates[0].device

    def connect(self) -> None:
        if self._serial and self._serial.is_open:
            return

        port = self._resolve_port()
        try:
            ser = serial.Serial(
                port=port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
                exclusive=True,
            )
        except TypeError:
            # pyserial on some platforms does not support `exclusive`.
            ser = serial.Serial(
                port=port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )

        self._active_port = port
        self._serial = ser

        # Give ESP32-C3 USB CDC time to settle after opening the port.
        time.sleep(self.config.boot_wait_s)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    @property
    def active_port(self) -> str | None:
        return self._active_port

    def _request_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.connect()
        assert self._serial is not None

        req = dict(payload)
        req_id = req.setdefault("id", str(uuid.uuid4()))
        raw = json.dumps(req, separators=(",", ":")) + "\n"

        self._serial.write(raw.encode("utf-8"))
        self._serial.flush()

        deadline = time.monotonic() + self.config.timeout
        while time.monotonic() < deadline:
            line = self._serial.readline()
            if not line:
                continue

            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded:
                continue

            try:
                resp = json.loads(decoded)
            except json.JSONDecodeError:
                continue

            if not isinstance(resp, dict):
                continue

            # Ignore boot/events in-band.
            if "event" in resp:
                continue

            if resp.get("id") != req_id:
                continue

            return resp

        port = self._active_port or self.config.port or "<unknown>"
        raise TimeoutError(f"timed out waiting for response on {port}")

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            last_error: Exception | None = None
            attempts = self.config.reconnect_retries + 1
            for attempt in range(attempts):
                try:
                    return self._request_once(payload)
                except (serial.SerialException, OSError, TimeoutError) as exc:
                    last_error = exc
                    self.close()
                    if attempt + 1 < attempts:
                        time.sleep(self.config.reconnect_backoff_s)
                        continue
                    break

            port = self.config.port or self._active_port or "auto"
            raise TransportError(f"serial request failed on port={port}: {last_error}")

    def call(self, cmd: str, **kwargs: Any) -> Any:
        payload = {"cmd": cmd, **kwargs}
        resp = self.request(payload)

        if not resp.get("ok", False):
            error = resp.get("error") or {}
            if isinstance(error, dict):
                raise DeviceError(
                    code=str(error.get("code", "unknown_device_error")),
                    message=str(error.get("message", "unknown device error")),
                    details=error.get("details") if isinstance(error.get("details"), dict) else {},
                    raw=resp,
                )
            raise DeviceError(code="unknown_device_error", message=str(error), raw=resp)

        return resp.get("result")


def config_from_env() -> SerialConfig:
    port = os.environ.get("ESP_GPIO_PORT") or None
    baud = int(os.environ.get("ESP_GPIO_BAUD", "115200"))
    timeout = float(os.environ.get("ESP_GPIO_TIMEOUT", "2.0"))
    boot_wait = float(os.environ.get("ESP_GPIO_BOOT_WAIT", "0.8"))
    retries = int(os.environ.get("ESP_GPIO_RETRIES", "2"))
    auto_port = os.environ.get("ESP_GPIO_AUTO_PORT", "1") not in {"0", "false", "False"}
    return SerialConfig(
        port=port,
        baudrate=baud,
        timeout=timeout,
        boot_wait_s=boot_wait,
        reconnect_retries=retries,
        auto_port=auto_port,
    )
