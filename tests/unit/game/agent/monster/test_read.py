"""monster read 的解析函数单元测试（`chaita/game/agent/monster/read.py`）。

真值来自规则：只留 name/hp/atk/def/exp/skills + 校验过的 icon_box。
"""

from chaita.game.agent.monster import read as monster_read


def test_clean_box_valid():
    assert monster_read._clean_box({"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}) \
        == {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}


def test_clean_box_invalid():
    assert monster_read._clean_box(None) == {}
    assert monster_read._clean_box({"x": 2, "y": 0, "w": 1, "h": 1}) == {}  # x 越界
    assert monster_read._clean_box({"x": 0, "y": 0, "w": 0, "h": 1}) == {}  # w = 0
    assert monster_read._clean_box({"x": 0, "y": 0, "w": 1}) == {}          # 缺 h


def test_parse_keeps_only_known_fields():
    rows = monster_read._parse(
        '{"monsters":[{"name":"红头怪","hp":"80",'
        '"icon_box":{"x":0.1,"y":0.1,"w":0.2,"h":0.2},'
        '"rank":"不该留"}]}')
    assert len(rows) == 1
    assert rows[0]["name"] == "红头怪"
    assert rows[0]["hp"] == "80"
    assert rows[0]["skills"] == ""
    assert "rank" not in rows[0]
    assert rows[0]["icon_box"] == {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}


def test_parse_bad_json():
    assert monster_read._parse("不是 json") == []
    assert monster_read._parse('{"别的":[]}') == []


# ---- 整个 read()：一次会话 + 空答案重试一次 + 按框裁图标 ----

class _Image:
    size = 4


class _Session:
    """假的 AI 会话：按顺序吐出准备好的回答。"""

    answers = []
    asked = []

    def __init__(self, prompt, tools=(), quiet=True, api_key=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ask(self, text, image=None, label=""):
        _Session.asked.append(label)
        return _Session.answers.pop(0), {}


def _patch(monkeypatch, answers, cutout=None):
    _Session.answers = list(answers)
    _Session.asked = []
    monkeypatch.setattr(monster_read.core, "Session", _Session)
    monkeypatch.setattr(monster_read.icons, "look_tool", lambda *a, **k: None)
    monkeypatch.setattr(monster_read.icons, "crop_cutout",
                        cutout or (lambda image, box: "icon.png"))
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_read_returns_empty_without_image(monkeypatch):
    _patch(monkeypatch, [])
    assert monster_read.read(None) == []
    assert monster_read.read(object()) == []     # 没有 size
    assert _Session.asked == []                  # 压根不该问模型


def test_read_parses_and_crops_icons(monkeypatch):
    _patch(monkeypatch, ['{"monsters":[{"name":"红头怪","hp":"80",'
                         '"icon_box":{"x":0.1,"y":0.1,"w":0.2,"h":0.2}}]}'])

    rows = monster_read.read(_Image(), api_key="k")

    assert [row["name"] for row in rows] == ["红头怪"]
    assert rows[0]["icon"] == "icon.png"
    assert "icon_box" not in rows[0]             # 框用完就丢，别带进数据
    assert _Session.asked == ["manual"]          # 一次就对，不用重试


def test_read_retries_once_when_answer_is_empty(monkeypatch):
    """模型第一次答歪了：同一个会话里再要一次，不重新发图。"""
    _patch(monkeypatch, ["我觉得是这样的：",
                         '{"monsters":[{"name":"红头怪"}]}'])

    rows = monster_read.read(_Image())

    assert [row["name"] for row in rows] == ["红头怪"]
    assert _Session.asked == ["manual", "manual_retry"]


def test_read_gives_up_after_retry(monkeypatch):
    _patch(monkeypatch, ["", "还是不给你 JSON"])

    assert monster_read.read(_Image()) == []
    assert _Session.asked == ["manual", "manual_retry"]


def test_read_counts_icons_that_could_not_be_cut(monkeypatch):
    _patch(monkeypatch, ['{"monsters":[{"name":"红头怪"},{"name":"铁卫"}]}'],
           cutout=lambda image, box: None)

    rows = monster_read.read(_Image())

    assert [row["icon"] for row in rows] == [None, None]   # 抠不出来也不丢怪
