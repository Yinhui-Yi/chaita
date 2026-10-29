"""读取失败时落一份现场，方便事后查。"""

import os
import time

from ..constants import _ASSETS


def _write_error_log(headline: str, detail: str) -> None:
    """把最近一次读取失败的原因写进 docs/capture/last_error.txt。

    界面上也会显示，但那样用户得截图给我；落一份文件我这边直接能看。
    """
    try:
        from ... import trace
        trace.note("read.error", headline=headline, detail=detail[:300])
    except Exception:
        pass
    try:
        root = os.path.dirname(_ASSETS)
        path = os.path.join(root, "docs", "capture", "last_error.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[%s] %s\n%s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"), headline, detail))
    except Exception:
        pass
