"""Small dependency-free regression test for Ecobulles water accounting."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "ecobulles" / "water_usage.py"
SPEC = spec_from_file_location("ecobulles_water_usage", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
WaterUsageState = MODULE.WaterUsageState


def main() -> None:
    state = WaterUsageState()

    assert state.apply_cycle_value(100) is False
    assert state.total_water_liters == 100

    assert state.apply_cycle_value(175) is False
    assert state.total_water_liters == 175

    assert state.apply_cycle_value(12) is True
    assert state.completed_cycles_liters == 175
    assert state.cycle_water_liters == 12
    assert state.total_water_liters == 187
    assert state.bottle_changes == 1

    assert state.apply_cycle_value(40) is False
    assert state.total_water_liters == 215

    restored = WaterUsageState.from_dict(state.as_dict())
    assert restored.total_water_liters == 215
    assert restored.bottle_changes == 1

    print("Water usage accounting checks passed.")


if __name__ == "__main__":
    main()
