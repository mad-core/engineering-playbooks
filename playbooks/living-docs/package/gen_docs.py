#!/usr/bin/env python3
"""Entry-point shim — all logic lives in _gen_docs/.

Lets the engine run without installing the package:
  python3 package/gen_docs.py <cmd>
The installed `gen_docs` console command (see pyproject) is the supported
interface and behaves identically.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _gen_docs.commands.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
