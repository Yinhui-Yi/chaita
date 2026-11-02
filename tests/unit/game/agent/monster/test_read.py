"""monster read 单元测试（`chaita/game/agent/monster/read.py`）。

真值来自规则：只留 name/hp/atk/def/exp/skills + 校验过的 icon_box；
图标由代码按**两遍精确定位**后的框直接裁（不抠图）：第一步给大概框 → 以它为中心裁小窗
一次发给模型 → 小图里的比例换算回整图 → 再问一遍更小的窗 → 略放宽后裁。
"""

import numpy as np
import pytest
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


# ---- 几何：放宽 / 小图比例换算回整图 ----

def test_grown_每边放宽框宽框高的一定倍数():
    box = {"x": 0.4, "y": 0.4, "w": 0.1, "h": 0.2}

    assert monster_read._grown(box, 0.5) == pytest.approx(
        {"x": 0.35, "y": 0.3, "w": 0.2, "h": 0.4})


def test_grown_夹在整图里_没有框就是空():
    grown = monster_read._grown({"x": 0.0, "y": 0.9, "w": 0.2, "h": 0.1}, 1.0)

    assert grown["x"] == 0.0 and grown["y"] == 0.8
    assert grown["x"] + grown["w"] <= 1.0 and grown["y"] + grown["h"] <= 1.0
    assert monster_read._grown({}, 0.5) == {}
    assert monster_read._grown(None, 0.5) == {}


def test_to_image_小图里的比例换算回整图():
    window = {"x": 0.2, "y": 0.4, "w": 0.2, "h": 0.1}
    inner = {"x": 0.5, "y": 0.0, "w": 0.25, "h": 1.0}

    box = monster_read._to_image(window, inner)

    assert box == pytest.approx({"x": 0.3, "y": 0.4, "w": 0.05, "h": 0.1})


def test_to_image_越出整图的部分夹掉():
    window = {"x": 0.9, "y": 0.9, "w": 0.1, "h": 0.1}

    box = monster_read._to_image(window, {"x": 0.5, "y": 0.5, "w": 1.0, "h": 1.0})

    assert abs(box["x"] + box["w"] - 1.0) < 1e-9
    assert abs(box["y"] + box["h"] - 1.0) < 1e-9


# ---- 整个 read()：一次会话 + 空答案重试一次 + 两遍精确定位 + 裁图标 ----

IMAGE = np.zeros((1000, 1000, 3), np.uint8)

ONE_MONSTER = ('{"monsters":[{"name":"红头怪","hp":"80",'
               '"icon_box":{"x":0.4,"y":0.4,"w":0.1,"h":0.1}}]}')
# 第一遍小窗是 x,y∈[0.35,0.55]、宽高 0.2：小图 (0.25,0.25,0.5,0.5) 正好是整图 (0.4,0.4,0.1,0.1)
PASS1 = '{"boxes":[{"i":1,"x":0.25,"y":0.25,"w":0.5,"h":0.5}]}'
# 第二遍小窗是 x,y∈[0.37,0.53]、宽高 0.16：小图 (0.1875,0.1875,0.625,0.625) 同样是整图 (0.4,0.4,0.1,0.1)
PASS2 = '{"boxes":[{"i":1,"x":0.1875,"y":0.1875,"w":0.625,"h":0.625}]}'


class _Session:
    """假的 AI 会话：按顺序吐出准备好的回答，记下每次问的标签和图的张数。"""

    answers = []
    asked = []
    images = []

    def __init__(self, prompt, tools=(), quiet=True, api_key=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ask(self, text, image=None, label=""):
        _Session.asked.append(label)
        _Session.images.append(
            [] if image is None else
            (list(image) if isinstance(image, (list, tuple)) else [image]))
        answer = _Session.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer, {}


def _patch(monkeypatch, answers):
    _Session.answers = list(answers)
    _Session.asked = []
    _Session.images = []
    monkeypatch.setattr(monster_read.core, "Session", _Session)
    monkeypatch.setattr(monster_read.icons, "look_tool", lambda *a, **k: None)
    # 单测不真跑抠图模型：只验证"裁哪一块"，抠图本身在 test_icons.py 里测
    monkeypatch.setattr(monster_read.icons, "_cutout", lambda crop: crop)
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def _side(icon):
    return icon.shape[1], icon.shape[0]


def test_read_returns_empty_without_image(monkeypatch):
    _patch(monkeypatch, [])
    assert monster_read.read(None) == []
    assert monster_read.read(object()) == []     # 没有 size
    assert _Session.asked == []                  # 压根不该问模型


def test_read_两遍精确定位后按精确框略放宽来裁(monkeypatch):
    _patch(monkeypatch, [ONE_MONSTER, PASS1, PASS2])

    rows = monster_read.read(IMAGE, api_key="k")

    assert [row["name"] for row in rows] == ["红头怪"]
    assert "icon_box" not in rows[0]             # 框用完就丢，别带进数据
    assert _Session.asked == ["manual", "icon_boxes", "icon_boxes"]
    # 精确框 (0.4,0.4,0.1,0.1) 每边往里收 6%（FINAL_GROW=-0.06，切掉白边）→ 宽高 0.088 → 88px
    width, height = _side(rows[0]["icon"])
    assert abs(width - 88) <= 1 and abs(height - 88) <= 1


def test_read_第二步把所有怪的小图一次发出去_不是一只一问(monkeypatch):
    two = ('{"monsters":[{"name":"红头怪","icon_box":{"x":0.4,"y":0.2,"w":0.1,"h":0.1}},'
           '{"name":"铁卫","icon_box":{"x":0.4,"y":0.6,"w":0.1,"h":0.1}}]}')
    _patch(monkeypatch, [two, '{"boxes":[]}', '{"boxes":[]}'])

    monster_read.read(IMAGE)

    assert _Session.asked == ["manual", "icon_boxes", "icon_boxes"]
    assert [len(images) for images in _Session.images] == [1, 2, 2]


def test_read_精确定位答歪了就退回第一步的框_略放宽(monkeypatch):
    _patch(monkeypatch, [ONE_MONSTER, "我看不清", "还是看不清"])

    rows = monster_read.read(IMAGE)

    # 第一步的框 (0.4,0.4,0.1,0.1) 放宽 FALLBACK_GROW=0.1 → 0.12 → 120px
    width, height = _side(rows[0]["icon"])
    assert abs(width - 120) <= 1 and abs(height - 120) <= 1


def test_read_第二遍没结果就保留第一遍的精确框(monkeypatch):
    _patch(monkeypatch, [ONE_MONSTER, PASS1, "第二遍答歪了"])

    rows = monster_read.read(IMAGE)

    width, height = _side(rows[0]["icon"])
    assert abs(width - 88) <= 1 and abs(height - 88) <= 1


def test_read_精确定位那一问报错_也不丢怪_退回第一步的框(monkeypatch):
    _patch(monkeypatch, [ONE_MONSTER, RuntimeError("网断了"), RuntimeError("网断了")])

    rows = monster_read.read(IMAGE)

    assert [row["name"] for row in rows] == ["红头怪"]
    assert rows[0]["icon"] is not None


def test_read_没有图标框的怪_图标是空_而且不发小图(monkeypatch):
    _patch(monkeypatch, ['{"monsters":[{"name":"红头怪"},{"name":"铁卫"}]}'])

    rows = monster_read.read(IMAGE)

    assert [row["icon"] for row in rows] == [None, None]   # 不丢怪
    assert _Session.asked == ["manual"]                    # 没有小窗就不多问


def test_read_retries_once_when_answer_is_empty(monkeypatch):
    """模型第一次答歪了：同一个会话里再要一次，不重新发图。"""
    _patch(monkeypatch, ["我觉得是这样的：",
                         '{"monsters":[{"name":"红头怪"}]}'])

    rows = monster_read.read(IMAGE)

    assert [row["name"] for row in rows] == ["红头怪"]
    assert _Session.asked == ["manual", "manual_retry"]


def test_read_gives_up_after_retry(monkeypatch):
    _patch(monkeypatch, ["", "还是不给你 JSON"])

    assert monster_read.read(IMAGE) == []
    assert _Session.asked == ["manual", "manual_retry"]


# ---- _refine：序号 / 校验 ----

class _OneShot:
    def __init__(self, answer):
        self.answer = answer
        self.sent = None

    def ask(self, text, image=None, label=""):
        self.sent = (text, image)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer, {}


def _quiet(monkeypatch):
    import chaita.trace as trace
    monkeypatch.setattr(trace, "note", lambda *a, **k: None)


def test_refine_不合法的小窗不发_也不占序号(monkeypatch):
    _quiet(monkeypatch)
    session = _OneShot('{"boxes":[{"i":1,"x":0.0,"y":0.0,"w":1.0,"h":1.0}]}')
    windows = [{}, {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2}]

    out = monster_read._refine(session, IMAGE, ["没框的怪", "有框的怪"], windows)

    assert out[0] == {}
    assert out[1] != {}                       # 序号 1 对的是第二只怪
    assert len(session.sent[1]) == 1          # 只发了一张小图
    assert "有框的怪" in session.sent[0] and "没框的怪" not in session.sent[0]


def test_refine_坏的框一律不要(monkeypatch):
    _quiet(monkeypatch)
    window = {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2}
    bad = ('{"boxes":['
           '{"i":9,"x":0.1,"y":0.1,"w":0.5,"h":0.5},'       # 序号越界
           '{"i":"x","x":0.1,"y":0.1,"w":0.5,"h":0.5},'     # 序号不是数字
           '{"i":1,"x":0.1,"y":0.1,"w":0.05,"h":0.5},'      # 太窄：当成瞎给
           '{"i":1,"x":1.5,"y":0.1,"w":0.5,"h":0.5},'       # 比例越界
           '"不是对象"]}')

    out = monster_read._refine(_OneShot(bad), IMAGE, ["怪"], [window])

    assert out == [{}]


def test_refine_模型出错就全部退回(monkeypatch):
    _quiet(monkeypatch)
    window = {"x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2}

    out = monster_read._refine(_OneShot(RuntimeError("断网")), IMAGE,
                               ["甲", "乙"], [window, window])

    assert out == [{}, {}]
