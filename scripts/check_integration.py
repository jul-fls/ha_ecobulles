"""Run lightweight local checks without a Home Assistant dev environment."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ok = compileall.compile_dir(ROOT / "custom_components" / "ecobulles", quiet=1)
    if not ok:
        return 1

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "test_water_usage_logic.py")],
        check=True,
        cwd=ROOT,
    )
    print("Integration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
