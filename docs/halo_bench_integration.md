# Halo Bench Integration Notes

This repo owns the low-level protocol and transport contract used by Halo bench
automation.

## Target controller board
- Controller reference board: <https://github.com/esp-rs/esp-rust-board>
- Current bring-up target: ESP32-C3 based board running this repo firmware.

## Carrier profile context
Downstream board mapping is maintained in `hardware-tools`, but this contract drives it.

Carrier: `SYC-00048-R00 Halo universal board, DVT2, test point carrier`
Header J2 canonical nets:
- 1 `S_CAPACITOR`
- 2 `LED_BLUE_PWM`
- 3 `BUTTON`
- 4 `LED_RED_PWM`
- 5 `GP45_TST_CMD`
- 6 `LED_GREEN_PWM`
- 7 `CAP_STATUS`
- 8 `GND`
- 9 `~RESET`
- 10 `GND`
- 11 `VBAT`
- 12 `VSYS`
- 13 `UART0_TX_PROT`
- 14 `UART0_RX_PROT`

## Firmware-reserved UART pins
Host UART bridge is reserved in firmware:
- RX: `GPIO20`
- TX: `GPIO21`

Downstream board abstractions must not repurpose these pins for direct GPIO drive.

## Direct-wire caveats
Current bench bring-up assumes direct 3.3 V logic for digital nets only.

Never drive these analog or rail nets directly from ESP32 GPIO:
- `S_CAPACITOR`
- `VBAT`
- `VSYS`

Use external instrumentation (`Saleae`, `PPK2`) for those nets.

## Cross-repo contract
- `esp32-mcp-io-extender`: protocol/transport/MCP + low-level API owner.
- `hardware-tools`: board-level mapping and semantic workbench API owner.
- `halo-rak11720-firmware`: scenario scripts owner; consumes `hardware-tools`.
