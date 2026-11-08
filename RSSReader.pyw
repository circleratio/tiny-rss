"""Double-click launcher: uses this file's folder as the data folder."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from rss_reader.__main__ import main  # noqa: E402

sys.exit(main(["--data-dir", str(HERE)]))
