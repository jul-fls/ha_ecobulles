"""Small dependency-free regression test for Ecobulles CO2 accounting."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "custom_components" / "ecobulles" / "co2_usage.py"
SPEC = spec_from_file_location("ecobulles_co2_usage", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CO2UsageState = MODULE.CO2UsageState


def main() -> None:
    """Verify that a raw reset does not erase prior injection time."""
    state = CO2UsageState()

    assert state.apply(100_000) == 100_000
    assert state.apply(120_000) == 120_000
    assert state.apply(500) == 120_500
    assert state.apply(2_000) == 122_000

    restored = CO2UsageState.from_dict(state.as_dict())
    assert restored.apply(3_000) == 123_000

    print("CO2 counter reset accounting checks passed.")


if __name__ == "__main__":
    main()
