"""仓库里所有"根目录"的唯一定义。

以前每个模块各自 `dirname×N` 数层数（src 少一层就全错）。现在只在这里算：
`ROOT` 是仓库根（chaita/ 的上一级），`LOGS` / `ASSETS` 都由它派生。
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
ASSETS = os.path.join(ROOT, "assets")
