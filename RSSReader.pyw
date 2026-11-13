"""Double-click launcher: uses this file's folder as the data folder."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from rss_reader.__main__ import main  # noqa: E402

# Prefer pythonw.exe so a pinned taskbar icon starts without a console
_exe = Path(sys.executable)
_pythonw = _exe.with_name("pythonw.exe")
if not _pythonw.exists():
    _pythonw = _exe

sys.exit(main(["--data-dir", str(HERE)], relaunch_command=f'"{_pythonw}" "{Path(__file__).resolve()}"'))
