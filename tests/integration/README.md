# 集成测试的标准（`tests/integration/`）

这一页是**判据**，不是建议。写/改这里的用例之前先对一遍；**对不上就删掉**，
不要"留着当参考"——留着会让下一次 review 重新数一遍同样的垃圾。

## 一、什么算集成测试

把两个以上**真组件**接起来跑，验证它们之间的**约定**成立。

- 被测的那条缝，两边都是真的：`Controller`(Python) ↔ QML 界面、QML 控件 ↔ 事件系统、
  界面 ↔ 存档文件。
- 只允许替身掉**被测缝之外**的东西：抓游戏窗口、AI 模型、系统剪贴板、屏幕尺寸。
- 断言的是**可观察结果**：窗口属性、界面上的文字、公开 Slot 返回的数据、磁盘上的文件。
  不是 `controller._map_history[0]["mons"]` 这种内部结构。

## 二、合格的用例长什么样

1. **用真事件驱动**：`helpers.click_item`（合成按下/抬起）、`sendEvent` 发
   `QMouseEvent/QKeyEvent`、`helpers.drop_cells`（合成 enter/move/drop 打真 `DropArea`）。
2. **只点用户点得到的东西**：按钮的 `objectName`、清单的行、地图的格子、坐标格。
3. **不调 QML 函数/Slot 代替操作**：`window.routeEnterCell(...)`、`window.addStairRow(...)`、
   `controller.saveStair(...)` 这类直调**不算集成**（它们只证明"函数调用后会变"）。
4. **断言公开结果**：`window.property("mapFloor")`、`controller.stairsOf(floor)`、
   `controller.routeCells(floor, 0)`、清单上的文字、`logs/` 里写出来的文件。
5. **允许摆起点数据**（`controller._map_history = [...]`、`controller._tasks = [...]`），
   但必须在文件头写清楚"这一段不覆盖读取链路"。
   **一条明确豁免**：造一条路线可以用 `window.storeRoute()` —— 它是唯一会生成链窗口需要
   的那份 ctx 结构的入口，而"真人怎么造路线"（地图长按拖）在 `test_cross_floor_*.py` 里
   已经覆盖了；路线链窗口那一份只关心"窗口里的按钮接对没接对"。
6. **注释写两件事**：`测什么：…` + `交互顺序：① … ② … ③ …`。
   **界面可以只有一扇**（都在同一个窗口里也没问题）—— 要交代的是**用户按什么顺序做了
   哪些动作**，因为"顺序"才是这份测试不肯放弃的信息，界面名字本身不说明什么。
   例：`交互顺序：① 怪物区里点那一行开卡片 ② 点缩略图开图库 ③ 图库点第一张 ④ 回卡片点保存`。

## 三、不合格的，一律删掉

- 直调 QML 函数/Slot 来触发行为（含 `_drag_on` 之类"帮用户走完"的捷径）。
- 纯函数/纯规则（`adjacentFloor`、`floorRank`、`_clean_stair`、`_stairs_list`…）——
  它们属于 `tests/unit/`，放在这里只是把单元测试伪装成集成测试。
- 只读/只改内部字段（`controller._map_history[i]["grid"]`、`controller._counters`…）
  而不经过界面。
- 断言"某函数被调用"、"某字段存在"，而不是用户在界面上能观察到的结果。
- 依赖真实机器状态（前台窗口、光标位置、剪贴板内容、磁盘上的旧存档）。

## 四、删之前先确认

删掉的规则要么已有单测覆盖（`tests/unit/`），要么在删的提交说明里写清**现在没人覆盖**。
宁可少一条测试，也不要留一条假的。

## 五、现状（逐步清）

| 文件 | 状态（条数 前→后） |
|---|---|
| `ui/controller/floors/test_cross_floor_route.py` | 13 → 4，删直调 `routeEnterCell`/`adjacentFloor`/`addStairRow` 的 |
| `ui/controller/floors/test_grid_multi_select.py` | 7 → 1，删直调 `gridMultiToggle`/`gridAssignMany` 的 |
| `ui/controller/test_route_compare.py` | 13 → 11：开窗/粘贴/清空/关窗全部改成点按钮，删 3 条直调 |
| `ui/controller/floors/test_cross_floor_usage.py` | 9 条都合格；`openMapSheet()` 直调改成点「清单 ›」，逐条补上「测什么 + 走过哪些界面」 |
| `ui/controller/test_main_columns_controls.py` | 14 → 12：删直调 `monDragStart/Finish` 的 1 条、合并两条选层用例；`selectFloor/showMap/stepFloor` 全改成点侧栏行/折叠头；断言换成公开属性 |
| `ui/controller/test_main_panel_controls.py` | 3 条都合格，补「测什么 + 走过哪些界面」，断言换成 `statusData` |
| `ui/controller/floors/test_route_window_controls.py` | 14 → 8：删掉 6 条"证明不了点击写进去了"的（1 条假通过 + 5 条换起点后写不回去）。探针已确认箭头点击会把 `ctx.menuCell` 设对，问题在 `routeFill → saveRouteCell` 写回；这 6 条规则**现在没有可信覆盖** |
| `ui/controller/floors/test_grid_click.py` | 6 → 5：删 `test_cell_at_outside_13x13_is_empty`（直调 `layer.cellAt()` 的纯函数检查，一次鼠标都没发）；编辑模式改成点「编辑」进，断言换成 `controller.gridCells(floor)` |
| `ui/controller/floors/test_floor_row_controls.py` | 6 条都合格；开窗改成点「清单 ›」（原来 `setProperty("floorWindows")` 硬开），断言换成 `window.sheetMons/sheetItems` |
| `ui/controller/test_session.py` | 2 条原来直调 `restoreSession()/discardSession()` → 改成点横幅按钮，断言换 `controller.monsters / sessionHint / window.sheetMons` |
| `ui/controller/test_battle_window_controls.py` | 15 条都合格；`openBattle()` 直调 → 点导航条 ⚔，`clipboardCopy()` 造数据 → 直接写替身剪贴板，`_last_status` 断言 → `statusData` |
| `ui/controller/test_window.py` | **整份删掉**：2 条都是直调 `animateSize() / dragStart() / dragEnd()` 再断言 `_anim_to / _drag_active` 私有字段，一次鼠标都没发；插值数学和光标换算在 `tests/unit/` 里。窗口拖动/动画的**入口**现在没有集成覆盖（无头环境驱动不了系统窗口拖动） |
| `ui/controller/test_monster_editor_controls.py` | 11 条都合格；断言换 `controller.monsters`，注释按新格式写「测什么 + 交互顺序」（① ② ③ …，可以全在同一扇卡片里） |
| `ui/controller/floors/test_floor_sheet_flow.py` | 9 条都合格；开窗改成点「清单 ›」（原来 `setProperty("floorWindows")` 硬开），断言换 `mapHistory/chatReply/tasks`，注释按「测什么 + 交互顺序」写 |
| `ui/controller/floors/test_floor_sheet_controls.py` | 8 条都合格；开窗改点「清单 ›」（顺带发现"开清单 = 自动进编辑模式"，两条用例的初始状态改成照实写），`gridEditToggle`/`assignGridCell` 直调换成点「完成」/真 drop 事件 |
| `ui/controller/monsters/test_drag_flow.py` | **整份删掉**：8 条全是直调 `monDragStart/_tick_mon_drag/monDragFinish` + 喂假光标 + 断言 `_mon_drag/monDragTo` 私有字段，一次界面事件都没有 —— 它测的是 `drag.py` 的规则，属于单测。其中两条（dpr 换算、读不到光标要收尾）已补进 `tests/unit/ui/controller/monsters/test_drag.py`；**真正的拖拽手感（系统光标 + 每帧读）没有自动化覆盖**（无头环境驱动不了） |
| `ui/controller/floors/test_floor_item_edit.py`、`test_floor_monster_edit.py` | **两份都删掉**（3 + 1 条）：只调 `addItemFull / setItemKind / addFloorMonsterFull` 这几个 Slot，一次界面都没有；这些槽在 `tests/unit/ui/controller/floors/test_items.py / test_monsters.py` 里覆盖得更多（含越界、空名字、没这层） |
| `ui/controller/reading/test_read_pipeline.py` | **整份删掉**（2 条）：直接调私有 `controller._deliver(...)`，没经过界面。它的规则在单测里有：`tests/unit/ui/controller/reading/test_deliver.py::test_deliver_monsters_aligns_floor_abbreviation`、"没读出层数不建层"并进了 `test_read_buttons` |
| `ui/controller/reading/test_read_buttons.py` | 3 → 4（多了"没读出层数"那条），断言换 `mapHistory/tasks/monsters/statusData/chatReply`，注释按「测什么 + 交互顺序」写 |
| `ui/controller/reading/test_read_chain.py` | **整份删掉**（4 条）：直调 `controller.readGame() / readOnly("map"/"monsters")`，而 `test_read_buttons` 已经从按钮走过同一条链（多了层数缺失那条）。"跑完不卡在读取中"的断言（`reading is False`、`activeReads == 0`）补进了按钮那份。**注意**：`readGame()` 现在没有任何界面入口（QML 里只有 `readMode` → `readOnly`），这条路**没人覆盖**，要留着它就得先给它一个按钮 |
| `ui/controller/floors/test_route_chain.py` | 3 条都合格；`assignGridCell()` 直调改成真 drop 事件（把格子拖到「铁卫」那一行），断言换 `mapHistory / routeCells`，注释按交互顺序写 |
| `ui/controller/floors/test_grid_edit.py` | 4 条按标准重写：全走真 drop 事件 / 右键「清掉」/ 关闭按钮（原来直调 `gridAssign`、`setProperty("gridEditOn")`、`closeFloorSheet`）；断言换 `gridCells/gridPositions/sheetMons/sheetItems`。**顺带查出**：同名资源要靠 `effect_manual` 才能保住各自的效果，否则界面按道具表统一成默认效果，两只就分不出来了 |
| `ui/controller/test_chat_dock.py` | 3 条都合格（真打字/真点发送）；断言换 `chatReply/statusData/chatting`，注释按交互顺序写 |
| `ui/controller/test_battle_window.py` | 2 条数值真值题改成真点击（开窗/问号菜单/切资源页/计算），去掉 `battleAddMonster/battleAddItem/battleComputePlan` 直调 |
| `ui/controller/test_battle_edit_card.py` | 4 条保留（真点图标开卡片/改数量/删/完成），`openBattle()` 直调 → 点导航条 ⚔ |
| `ui/controller/test_chat_status_chain.py` | 3 → 1：删掉两条和 `test_chat_dock`/`test_main_panel_controls` 重复的 Slot 直调；留下的"状态锁拦住读取"改成点锁图标 + 点刷新（原来直调 `toggleStatusLock` + 私有 `_deliver`） |
| `ui/controller/monsters/test_edit.py` | **整份删掉**（2 条）：直调 `addMonsterTpl / removeMonsterByName`，无界面；`tests/unit/ui/controller/monsters/test_edit.py` 里覆盖得更多（含空名字、按名字删各层） |
| `ui/test_startup_teardown.py` | 1 条保留：真 Controller + 真 QML 引擎跑 `_teardown`，断言窗口/引擎/controller 真的销毁。它触发是"进程退出"，没有可点入口 —— 在文件头写明了这是豁免，别再当"直调私有函数"删掉 |
| **全 30 个文件已过完** | 178 → **129 条**（删 8 个文件/22 条，其余改写或补注释）。旧的 `走过的界面` 写法还剩 4 个文件（cross_floor_route / grid_multi_select / route_compare / cross_floor_usage），后面碰到再换成「交互顺序」 |
