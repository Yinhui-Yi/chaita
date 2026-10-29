"""配置读取。

只做一件事：拿到 DeepSeek 的 API key。

不引入 yaml 依赖 —— 配置就一个键，为它多装一个包不划算
（`chaita` 环境里本来就没有 pyyaml）。
"""

import os

from .paths import ROOT
CONFIG_PATH = os.path.join(ROOT, "config.yaml")


def api_key() -> str:
    """优先环境变量 DEEPSEEK_API_KEY，其次项目根目录 config.yaml 的 api_key 行。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                name, _, value = line.partition(":")
                if name.strip() != "api_key":
                    continue
                return value.strip().strip('"').strip("'")
    except FileNotFoundError:
        return ""
    except Exception:
        return ""
    return ""
