from __future__ import annotations

from pathlib import Path

from esp32_mcp_io_extender.named_endpoints import load_endpoint_config


def test_halo_syc_00048_r00_dvt2_endpoint_config_loads() -> None:
    path = Path("configs/halo_syc_00048_r00_dvt2_endpoints.json")

    config = load_endpoint_config(path)

    assert config.resolve("reset_n").pin == 4
    assert config.resolve("button").tools[0].name == "halo_button_press"
    assert config.resolve("gp45_tst_cmd").capabilities == ("digital_out",)
    assert config.resolve("cap_status").capabilities == ("digital_in",)
