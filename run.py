"""ChaitaAssistant 启动入口。

    python run.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chaita.ui.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
