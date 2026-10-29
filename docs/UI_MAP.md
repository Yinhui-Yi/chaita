# UI 地图：哪个界面在哪份文件、状态在谁身上

> 界面从「七千多行一个文件」拆到现在：`MainWindow.qml` **2512 行**，一共 22 个 QML 文件
> （9316 行），一个界面一个文件夹。这一页是拆完后的结构，改代码前对照。

---

## 1. 界面清单（主窗口 1 + 主窗口三块 3 + 子界面 13 = 17 个界面，另有 5 个共用件）

| # | 子界面 | 类型 | 文件 | 状态在谁身上 | 怎么打开 |
|---|---|---|---|---|---|
| 1 | 主窗口 | 真窗口 | `views/MainWindow.qml` | 它自己（`win.*`） | 程序启动 |
| 2 | 导航条 / 抬头 / 状态行 | 主窗口的一块 | `views/main_panel/MainPanel.qml` | 主窗口；对外只给 `chromeBottom` | 常驻 |
| 3 | 三栏 + 读取记录 | 主窗口的一块 | `views/main_columns/MainColumns.qml` | 主窗口（`floorList/monRows/skills/…Collapsed`）；外层用 id `body` 量高度 | 常驻（在 `flick` 里滚） |
| 4 | 底部对话 | 主窗口的一块 | `views/chat/ChatDock.qml` | 主窗口；对外给 `logHeight` / `inputFocused` | 常驻 |
| 5 | 「这一层」小窗 | 真窗口（每层一个） | `views/floor_sheet/FloorSheetWindow.qml` | 主窗口 `floorWindows/floorPositions/floorSizes/floorSheets` | 点地图块 |
| 6 | 加怪 / 加资源下拉 | 覆盖层 z=58 | `views/floor_sheet/pick_menu/PickMenu.qml` | 主窗口 `pickMode/pickFloor/pickMenuX/Y`；`sheetName` 由宿主递 | 点「＋ 加怪 / ＋ 加资源」 |
| 7 | 路线层 | 地图上的覆盖层 | `views/floor_sheet/route_layer/RouteLayer.qml` | 它自己（`cells/editing`）；松手交给主窗口 `storeRoute()` | 在「这一层」的图上长按玩家 |
| 8 | 格子编辑层 | 地图上的覆盖层 | `views/floor_sheet/grid_layer/GridLayer.qml` | 它自己（`editing` / `gridCells` / `dragging`）；松手把坐标记给宿主 | 「这一层」进编辑模式后在地图上画 13×13、长按抓格子拖到词条上 |
| 9 | 伤害计算 | 真窗口 | `views/battle_calc/BattleWindow.qml` | 主窗口 `battle*` | 导航条 ⚔ |
| 10 | 改参数卡片（伤害计算） | 覆盖层 z=30 | `views/battle_calc/edit_card/EditCard.qml` | 主窗口 `battleEdit*` | 点链上缩略图 |
| 11 | 问号菜单 | 覆盖层 z=20 | `views/battle_calc/pick_menu/PickMenu.qml` | 主窗口 `battleMenu*/battlePick*` | 点问号 / 箭头 |
| 12 | 怪物编辑 | 覆盖层 z=60 | `views/monster_editor/MonsterEditor.qml` | 主窗口 `monEdit/monDraft/monSkills`；自带 `fill()/commit()/iconAnchorBox()/skillAnchorBox()` | 点怪物那一行 |
| 13 | 素材库选图 | 覆盖层 z=70 | `views/icon_picker/IconPicker.qml` | 主窗口 `iconPicker/iconQuery/iconMenuX/Y`；搜索框自己清 | 点怪物头像 |
| 14 | 技能挑选 | 覆盖层 z=72 | `views/skill_picker/SkillPicker.qml` | 主窗口 `skillPicker/skillMenuX/Y`；选中走 `pick()`，摆位走 `placeUnder(box)` | 点「加技能」 |
| 15 | 路线链 | 真窗口 | `views/route_editor/RouteWindow.qml` | 主窗口 `route*`（哪一层、第几条、格子副本、结果） | 地图上松手 / 点「这一层」清单里的路线 |
| 16 | 改参数卡片（路线链） | 覆盖层 z=30 | `views/route_editor/edit_card/EditCard.qml` | 主窗口 `routeEdit*` | 点链上缩略图 |
| 17 | 一格填什么 | 覆盖层 z=20 | `views/route_editor/pick_menu/PickMenu.qml` | 主窗口 `routeMenu/routeMenuCell/routePick*` | 点链上的格子 |

（1 是主窗口本体，2–4 是它的三块，5 以后是它的子界面。`views/shared/` 那 5 个是共用件，不算界面。）

**规矩**：状态都放在**主窗口**（`win.*`）；子界面只画和点，读 `host.xxx`。
`host` 由宿主写死：主窗口里 `Xxx { host: win }`，伤害计算里 `Xxx { host: battleWin.host }`。
配色/字体直接 `Theme.xxx`（`views/shared/Theme.qml` 单例），不再从宿主绕。

---

## 2. 目录与行数（`sum(1 for _ in open(p))`，含空行）

```
chaita/ui/
    views/                        22 个 QML / 9315 行（+ shared/qmldir），只有界面
        MainWindow.qml            2512   棋盘/卡片/滚动容器 + win.* 状态和函数
        main_panel/                290   导航条 + 抬头 + 状态行
        main_columns/              891   地图/怪物/技能/读取记录（id 仍叫 body）
        chat/                      163   底部对话（sendChat/scrollChatToEnd/logHeight）
        monster_editor/            680   怪物编辑（fill/commit/iconAnchorBox/skillAnchorBox）
        icon_picker/               280   素材库选图
        skill_picker/              126   技能挑选（pick/placeUnder）
        floor_sheet/              1510   「这一层」小窗（FloorSheetWindow 1054 + 下面三块）
            route_layer/           151   地图上的路线提取层（长按/拖动/红底红框）
            grid_layer/            175   格子编辑层（13×13 坐标线、长按抓格子）
            pick_menu/             130   加怪/加资源下拉
        battle_calc/              1388   伤害计算窗口（BattleWindow 843 + 下面两块）
            edit_card/             363   改参数卡片
            pick_menu/             182   问号菜单
        route_editor/             1092   路线链（RouteWindow 534 + 下面两块）
            edit_card/             355   改参数卡片（路线链版，和伤害计算同一长相）
            pick_menu/             203   一格填什么（怪/资源/门/清空）
        shared/                    383   NumberStepper 188 + EffectEditor 80 + ChainArrow 54 + FlatBtn 38 + Theme 24 + qmldir
    main.py  startup.py  loader.py  constants.py  qt_env.py
                                      入口 / 启动 / 加载(QML_DIR, OVERLAY_QML) / 常量 / Qt 路径
    controller/                  30 个文件 / 2963 行，状态和槽（Python）
        controller.py                  Controller 本体：Property + 组合
        jobs.py  window.py  session.py 线程 / 窗口 / 会话
        reading/     tasks deliver scan items common mixin      读图、读手册
        monsters/    read icons edit drag mixin                 怪物记录/图标/增删改/拖动
        floors/      records items monsters routes feedback common mixin
                                                       每层记录/资源行/本层的怪/路线链/回执
        status.py  chat.py  battle.py                           人物面板 / 对话 / 伤害计算数据
    toolkit/                      纯函数小工具（不碰窗口）
```

---

## 3. 对应关系（views 一份 ↔ controller 一份）

| views 文件夹 | controller 那一份 | 管什么 |
|---|---|---|
| `main_panel/` | `status.py`（`StatusMixin`） | `statusText` `attrText` `itemsText` `goldText` `statusData` `updateStatus` |
| `chat/` | `chat.py`（`ChatMixin`） | `chatLog` `chatReply` `chatting` `errorText`、`sendChat()` |
| `battle_calc/` | `battle.py`（`BattleMixin`） | `battleHero` `battleMonsters` `battleItems`、`computeBattle()` |
| `route_editor/` | `floors/routes.py`（`RoutesMixin`） | 路线的存/改/删（`saveRoute` `saveRouteCell` `removeRoute`）+ 用地图记录预填 |
| `main_columns/` | `reading/` + `floors/` | 读取记录 / 每层地图和资源 |
| `monster_editor/` `icon_picker/` `skill_picker/` | `monsters/` | 怪物记录、图标、增删改、拖动 |

一个概念一个文件（status/chat/battle），十几个函数就一个包——只有这一条判断标准。
`views/MainWindow.qml` 这 2512 行是 `card` 容器、`flick` 滚动容器、各子界面挂载点
和 `win.*` 状态/函数，**属于主窗口本体**，不再拆。

**机制**：`tools/check_scenarios.py` 把每个场景渲染一遍、抓 QML 运行期警告
（`Unable to assign` / `TypeError` / `is not defined`）——`host.xxx` 没定义、跨文件抓 id
（`mapGrid` / `skillBtn` / `flick.width` 这类拆文件漏下的引用）都会在这儿现形；界面确实能点、
点出正确结果，由 `tests/integration/` 用真窗口再确认一遍。

---

## 4. 名字约定

- 文件名 = QML 类型名（PascalCase）；文件夹小写下划线（功能名，不是文件类型名）。
- `objectName` 前缀：`xxxBtn / xxxLayer / xxxDialog / xxxRow / xxxChevron / xxxField`。
- 界面之间只通过三样东西说话：`host`、`Theme`、宿主显式给的属性
  （`sheetName` / `logHeight` / `inputFocused` / `chromeBottom` / `iconAnchorBox()` /
  `skillAnchorBox()` / `placeUnder()`）。
- 跨文件不许抓别人的 `id`（也不许 `host: host` 这种自引用——那会变成 undefined）；
  要数据就在对方文件里开一个函数/属性。
- **数字框一律用 `views/shared/NumberStepper.qml`**（框 + ▲▼，按住连加/连减，
  也能直接打字）：`fieldName` 一并决定 objectName —— 整个框 = `fieldName + "Box"`，
  输入框 = `fieldName`，箭头 = `fieldName + "Up"` / `+ "Down"`。
  **箭头平时藏着**（鼠标移上来或拿到焦点才淡入，位置一直留着，出现时不跳）；
  它只在**松手/打完字**时发一次 `committed(text)`，按住连加不会一路往会话文件里写。
  宽度按"一个数字 + 两个箭头"给（34），别再拉成一长条。
- **资源效果一律用 `views/shared/EffectEditor.qml`**：一段一条「属性 + 加减号 +
  数字框」，属性写死、**每段数字都能改**（黄宝石三样一起加就三条）。
  使用方给 `parts`（`controller.itemEffectPartList(effect)`）和 `fieldName`；
  第 1 段用原名（`xxxLabel`/`xxxSign`/`xxx`），第 2 段起加序号（`xxxLabel1`…），
  同一条里属性列取最宽的那个，数字列因此对得齐。「这一层」资源行和伤害计算的
  改参数卡片用的是**同一个控件**，改一处两边都变。
