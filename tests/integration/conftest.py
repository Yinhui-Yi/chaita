"""集成测试的公共夹具。"""

import pytest


@pytest.fixture(autouse=True)
def _不碰用户的窗口状态文件(monkeypatch):
    """集成测试里点「置顶」/ 收起对话 / 拖窗口，都会走 `_save_ui_state` 写 logs/ui_state.json。
    测试不许改用户真正的窗口状态，所以一律关掉（`CHAITA_NO_UI_STATE` 见 toolkit/state.py）。"""
    monkeypatch.setenv("CHAITA_NO_UI_STATE", "1")
