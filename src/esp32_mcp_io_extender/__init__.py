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
    "BoardSignal",
    "HaloBoardWorkbench",
    "HaloWorkbenchConfig",
    "SignalPolarity",
]
