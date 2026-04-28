"""ESP32 MCP IO Extender Python API."""

from .bridge import (
    PROTOCOL_NAME,
    CapabilitySnapshot,
    DetectedDevice,
    DeviceError,
    EspGpioBridge,
    GpioBridgeError,
    PortCandidate,
    SerialConfig,
    TransportError,
    config_from_env,
)
from .uart_pty import (
    UartPtyManager,
    uart_pty_start,
    uart_pty_status,
    uart_pty_stop,
)
from .workbench import (
    BoardSignal,
    HaloBoardWorkbench,
    HaloWorkbenchConfig,
    SignalPolarity,
)

__all__ = [
    "PROTOCOL_NAME",
    "CapabilitySnapshot",
    "DetectedDevice",
    "DeviceError",
    "EspGpioBridge",
    "GpioBridgeError",
    "PortCandidate",
    "SerialConfig",
    "TransportError",
    "config_from_env",
    "UartPtyManager",
    "uart_pty_start",
    "uart_pty_stop",
    "uart_pty_status",
    "BoardSignal",
    "HaloBoardWorkbench",
    "HaloWorkbenchConfig",
    "SignalPolarity",
]
