# 测试规范

> 追求和代码一样：**合理优雅** —— 真值一处、规则一处、不为改动最小。
> 本文是写测试的唯一流程，写之前先读，不许凭记忆抄旧 test。

## 0. 边界

- 工作范围：**只碰 ChaitaAssistant 这一个项目**（`chaita/`、`tests/`、`docs/`、`tools/`、`assets/`、`logs/`）。
- **不碰** mt1005、mota、别的塔、别的引擎。
- 旧的 test 全是狗屎：**不读、不搬、不留**，从零重写。

## 1. 测试第一步：明确测试对象

- 对象 = `chaita/` 源码里的**对外契约**（函数 / `@Slot` / 数据格式）。
- 找对象 = **读源码**枚举，不是凭记忆列、不是列函数名凑数。
- 写单元测试**必须先读实现**：入参、返回值、边界、异常分支、依赖谁。

## 2. 单元测试流程

1. 读代码，定位**一个**对外契约（一个函数 / 一个 Slot）。
2. 读实现，列输入域（正常 / 边界 / 异常）和它的依赖。
3. **把依赖全部隔离**（stub / fake 替掉）。
4. 从规格定正确输出。
5. 写断言：每个输入 → 期望。
6. **先红**，红了判断改代码还是改期望，只改一边。

## 3. 集成测试流程

1. 读代码，定位**一条跨模块链路**（点按钮 → controller Slot → game 函数 → 状态变了）。
2. 读链路里每个环节的接口约定。
3. **被测的那条缝两边都真**（真 Controller + 真 QML + 真事件）；只桩**边界之外**的东西
   （抓游戏窗口、AI 模型、系统剪贴板）。
4. 从规格定**整条链路的最终结果**。
5. 驱动必须是**用户能做的动作**：`click_item` / `sendEvent(QMouseEvent/QKeyEvent)` /
   `drop_cells`（合成 enter/move/drop 打真 `DropArea`）。**不许直调 QML 函数或 Slot**
   （`window.routeEnterCell(...)`、`controller.saveStair(...)` 这种只证明"函数调用后会变"）。
6. 断言读**公开结果**：窗口属性、界面文字、公开 Slot 返回（`mapHistory / tasks /
   monsters / gridCells / routeCells / sheetMons`），不读 `controller._xxx` 内部字段。
7. 起点数据可以直接摆（`controller._map_history = [...]`），但文件头要写清"这一段不覆盖
   读取链路"；注释写**测什么 + 交互顺序 ① ② ③**（界面可以只有一扇，顺序才是要交代的）。
8. **不合上面任何一条的，删掉**（不要留着当参考）—— 判据和已有豁免见
   `tests/integration/README.md`。
9. 先红后绿：红了改代码或改期望，只改一边。

## 4. 两者的区别

| | 对象 | 依赖 | 驱动方式 | 断言粒度 |
|---|---|---|---|---|
| 单元 | 单个契约 | 全部隔离 | 直接调 | 单函数输出 |
| 集成 | 跨模块链路 | 真实（边界除外用桩） | 真事件（点击/打字/拖放） | 整条链路最终状态 |

## 5. 期望值从哪来（oracle）

- **伤害**：`battle.py` 文档里的公式（对着 xinxin2 引擎核过的那套）。
- **数据**：`assets/` 里的数据文件（`monster_templates.json`、`iteminfo`）。
- **读取**：`docs/capture/` 的截图 + 人工核过的真值。
- **禁止**：`expected = 调自己的函数`（`run_plan` / `computeBattle` 当标准答案）；禁止拿英雄血量当伤害。

## 6. 框架与目录

- 框架：**pytest** + **pytest-mock**（依赖隔离）+ **pytest-cov**（找漏网，不当标准）。
- 目录：

```
tests/
├── oracle.py          # 真值唯一入口
├── fixtures/          # 真值数据（damage_truth.json / read golden）
├── unit/              # 镜像 chaita/ 目录结构
│   ├── game/          # chaita/game/ 的镜像
│   └── ui/            # chaita/ui/ 的镜像
└── integration/       # 真实链路
```

- 镜像规则：`chaita/x/y/z.py` → `tests/unit/x/y/test_z.py`，层级、文件名一一对应，不许合并、不许缩水。

## 7. 纪律

- **先红后绿**：修 bug / 加功能，先写一条必红的测试，再改代码。
- 覆盖率只是仪表盘，**判对错靠 oracle，不靠覆盖率数字**。
- 判对错 = 差分 / 手推规则，不是抄代码输出。
