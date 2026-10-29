"""API key 转发单元测试（`chaita/ui/toolkit/api.py`）。

真值来自规则：这里只转发 `chaita.config.api_key()`，不自己另存一份。
"""

import chaita.ui.toolkit.api as api


def test_api_key_forwards_to_config(monkeypatch):
    import chaita.config as config
    monkeypatch.setattr(config, "api_key", lambda: "sk-x")
    assert api._api_key() == "sk-x"
