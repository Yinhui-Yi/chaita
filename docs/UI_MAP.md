# UI 地图：哪个界面在哪份文件、状态在谁身上

> 界面从「七千多行一个文件」拆到现在：`MainWindow.qml` **3688 行**，一共 39 个 QML 文件
> （14036 行），一个界面一个文件夹。这一页是拆完后的结构，改代码前对照。
> 2026-11-01 起主界面是**灰底窗口 + 白卡片**（见下面「视觉规矩」）。

---

## 1. 界面清单（主窗口 1 + 主窗口四块 4 + 子界面 14 = 19 个界面，另有 12 个共用件）

| # | 子界面 | 类型 | 文件 | 状态在谁身上 | 怎么打开 |
|---|---|---|---|---|---|
| 1 | 主窗口 | 真窗口 | `views/MainWindow.qml` | 它自己（`win.*`） | 程序启动 |
| 2 | 导航条 / 抬头 / 状态行 | 主窗口的一块 | `views/main_panel/MainPanel.qml` | 主窗口；对外只给 `chromeBottom` | 常驻 |
| 3 | 四张卡（地图 / 怪物 / 技能 / 读取记录）+ 上次记录横幅 | 主窗口的一块 | `views/main_columns/MainColumns.qml`（摞卡）+ `MapSection` / `MonSection`（一行 36px：只有头像、名字、「剩 N」、✕）/ `SkillSection`（一排胶囊，放不下换行；点一颗弹技能介绍卡：手册原话可改写、没有的自己写，存在 `logs/skill_notes.json`）/ `TaskSection` | 主窗口（`floorList/monRows/skills/…Collapsed/skillIntroOpen`）；外层用 id `body` 量高度 | 常驻（在 `flick` 里滚） |
| 4 | 地图（主界面那一栏） | 主窗口的一块 | `views/map_view/MapPanel.qml` | 主窗口 `mapFloor/mapHint/gridEditOn/gridEditFloor/mapHi*`；侧栏报 `selectFloor`/`stepFloor` | 常驻（折叠/展开在那栏的标题上） |
| 5 | 底部对话（标题行可收起 + 气泡 + 圆角输入栏，纸飞机发送键，你靠右 / AI 靠左，时间常显） | 主窗口的一块 | `views/chat/ChatDock.qml` | 主窗口 `chatCollapsed`（记在 `ui_state.json`）；对外给 `logHeight` / `inputFocused`；高度 `dockH` = 标题行 `chatHeadH` +（展开时）输入栏 `chatBarH` + 有对话时的气泡区 | 常驻 |
| 6 | 路线层 | 地图上的覆盖层 | `views/map_view/route_layer/RouteLayer.qml` | 它自己（`cells/editing`）；每走一格报 `stepped(cell)`，短按报 `tapped(cell)`，松手交给主窗口 `storeRouteCells()` | 在地图上长按玩家（画路线）/ 点一下楼梯（换层） |
| 7 | 格子编辑层 | 地图上的覆盖层 | `views/map_view/grid_layer/GridLayer.qml` | 它自己（`editing` / `gridCells`）；单击报 `cellPicked(row,col)`、Ctrl 多选、右键报 `menuRequested(row,col,x,y)` | 地图那栏「编辑」后画 13×13；单击选中、Ctrl 多选、右键出小窗（复制坐标 / 清掉） |
| 8 | 楼梯层 | 地图上的覆盖层 | `views/map_view/stair_layer/StairLayer.qml` | `stairs` / `cell` / `upSrc` / `downSrc`（**纯显示**，不接管鼠标） | 常驻；要改楼梯去「这一层」清单的楼梯区 |
| 9 | 「这一层」小窗（清单） | 真窗口（每层一个） | `views/floor_sheet/FloorSheetWindow.qml` | 主窗口 `floorWindows/floorPositions/floorSizes/floorSheets` | 点路线行 / `openFloorSheet()`；**不含地图** |
| 10 | 加怪 / 加资源下拉 | 覆盖层 z=58 | `views/floor_sheet/pick_menu/PickMenu.qml` | 主窗口 `pickMode/pickFloor/pickMenuX/Y`；`sheetName` 由宿主递 | 点「＋ 加怪 / ＋ 加资源」 |
| 11 | 伤害计算 | 真窗口 | `views/battle_calc/BattleWindow.qml` | 主窗口 `battle*` | 导航条 ⚔ |
| 12 | 改参数卡片（伤害计算） | 覆盖层 z=30 | `views/battle_calc/edit_card/EditCard.qml` | 主窗口 `battleEdit*` | 点链上缩略图 |
| 13 | 问号菜单 | 覆盖层 z=20 | `views/battle_calc/pick_menu/PickMenu.qml` | 主窗口 `battleMenu*/battlePick*` | 点问号 / 箭头 |
| 14 | 怪物编辑 | 覆盖层 z=60 | `views/monster_editor/MonsterEditor.qml` | 主窗口 `monEdit/monDraft/monSkills`；自带 `fill()/commit()/iconAnchorBox()/skillAnchorBox()` | 点怪物那一行 |
| 15 | 素材库选图 | 覆盖层 z=70 | `views/icon_picker/IconPicker.qml` | 主窗口 `iconPicker/iconQuery/iconMenuX/Y`；搜索框自己清 | 点怪物头像 |
| 16 | 技能挑选 | 覆盖层 z=72 | `views/skill_picker/SkillPicker.qml` | 主窗口 `skillPicker/skillMenuX/Y`；选中走 `pick()`，摆位走 `placeUnder(box)` | 点「加技能」 |
| 17 | 路线链 | 真窗口 | `views/route_editor/RouteWindow.qml` | 主窗口 `route*`（哪一层、第几条、格子副本、结果） | 地图上松手 / 点「这一层」清单里的路线 |
| 18 | 改参数卡片（路线链） | 覆盖层 z=30 | `views/route_editor/edit_card/EditCard.qml` | 主窗口 `routeEdit*` | 点链上缩略图 |
| 19 | 一格填什么 | 覆盖层 z=20 | `views/route_editor/pick_menu/PickMenu.qml` | 主窗口 `routeMenu/routeMenuCell/routePick*` | 点链上的格子 |
| 20 | 路线对比 | 真窗口 | `views/route_compare/CompareWindow.qml` | 主窗口 `compare*`（几条路线 + 各自算好的结果） | 导航条 ⇄（伤害计算右边） |
| 21 | 加属性收益 | 真窗口 | `views/property_gain/GainWindow.qml` | 主窗口 `gain*`（三档加成 + 上界 + 结果）；窗口自己只有窗口状态 | 导航条 ＋（⚔ 左边） |

（1 是主窗口本体，2–5 是它的块，6 以后是它的子界面。`views/shared/` 那些是共用件，不算界面：
`Theme` 配色/字体/圆角/控件高度、`FlatBtn` 方按钮、`TextBtn` 小文字按钮、`IconBtn` 图标按钮（导航条）、
`SectionHead` 分区标题条（地图/怪物/技能/读取记录）、`ReadBtn` 分区标题上的「读取」、`Card` 白卡、`Chip` 小胶囊、`NumberStepper` 加减数、
`EffectEditor` 效果编辑、`ChainArrow` 链箭头、`CoordField` 一格坐标、`FloorField` 层号格。）

**视觉规矩（2026-11-01 重做，PyCharm 浅色一路 + 分层）**：三层面——灰底窗口（`Theme.canvas`）→
白色卡片（`shared/Card.qml`：圆角 8 + 细外框 + 底沿一线暗边）→ 卡里凹下去的小块（`Theme.tile`）；
窗口最外圈留 `win.inset` 的透明边画投影，所以**弹层摆位一律按 `win.cardW / cardH` 和卡片坐标算，
不是窗口宽高/场景坐标**。字号分档：塔名 17 / 卡标题 14 / 正文 12–13 / 说明 10–11，数字用等宽。
**唯一一个强调蓝**，只给主操作和当前状态；小标签用 `shared/Chip.qml`。
按钮/输入框/图标按钮同高 `Theme.controlH`（24），圆角 `Theme.radius`（4），悬停才出浅灰底。
颜色/圆角**只从 `Theme` 取，不在界面里写十六进制**。
`Theme.amber` / `amberInk` 是旧名字（现在是强调蓝），逐个窗口换样式时改成 `accent`。

**地图就在主界面那一栏里画**（用户 2026-10-30："把主界面的地图做大！"、"多张地图不要
重叠显示下层的只留一角！做侧边栏快速切换"）：左边侧栏一层一行（写层号 + 剩几只，点了
切层），右边一张**大图**只画这一层，其余层压在大图后面、只露右下角一条（`peekMax = 1`，
用户："不要叠太多"）。截图、路线层、格子编辑层、楼梯、对比高亮都画在这一份上；
「这一层」小窗只剩清单。

**规矩**：状态都放在**主窗口**（`win.*`）；子界面只画和点，读 `host.xxx`。
`host` 由宿主写死：主窗口里 `Xxx { host: win }`，伤害计算里 `Xxx { host: battleWin.host }`。
配色/字体直接 `Theme.xxx`（`views/shared/Theme.qml` 单例），不再从宿主绕。

---

## 2. 目录与行数（`sum(1 for _ in open(p))`，含空行）

```
chaita/ui/
    views/                        39 个 QML / 14036 行（+ shared/qmldir），只有界面
        MainWindow.qml            3688   灰底窗口 + 外阴影 + 滚动容器 + win.* 状态和函数
        main_panel/                349   导航条（工具图标 + 置顶）+ 状态卡（塔名/四个数值块/钥匙胶囊）
        main_columns/              913   摞卡：MainColumns + MapSection / MonSection / SkillSection / TaskSection
        chat/                      301   底部对话（标题行可收起 + 气泡 + 输入栏）
        map_view/                 1198   地图（主界面那一栏 + 三个图层）
            MapPanel.qml           675   侧栏切层 + 单层大图 + 叠在后面的一角 + 编辑/清单
            stair_layer/           103   楼梯层（一层几个楼梯的徽章，纯显示）
            route_layer/           278   路线提取层（长按画线/跨层/短按报 tapped）
            grid_layer/            142   格子编辑层（13×13 坐标线、单击选中、右键小窗）
        monster_editor/            710   怪物编辑（fill/commit/iconAnchorBox/skillAnchorBox）
        icon_picker/               296   素材库选图
        skill_picker/              135   技能挑选（pick/placeUnder）
        floor_sheet/              1425   「这一层」小窗（FloorSheetWindow + 下拉）
            pick_menu/             138   加怪/加资源下拉
        battle_calc/              1459   伤害计算窗口 + 改参数卡片 + 问号菜单
            edit_card/             372   改参数卡片
            pick_menu/             187   问号菜单
        route_editor/             1186   路线链 + 改参数卡片 + 一格填什么
            edit_card/             363   改参数卡片（路线链版，和伤害计算同一长相）
            pick_menu/             210   一格填什么（怪/资源/门/清空）
        route_compare/             509   路线对比（几条路线并排比每只怪掉血）
        property_gain/             813   加属性收益（再加 X 点属性，剩下的怪少掉多少）
        preview/                    90   看大图
        shared/                    964   Theme + Card + Chip + SectionHead + ReadBtn + IconBtn + FlatBtn + TextBtn
                                         + NumberStepper + EffectEditor + ChainArrow + CoordField + FloorField + qmldir
    main.py  startup.py  loader.py  constants.py  qt_env.py
                                      入口 / 启动（任务栏图标、分组 ID）/ 加载(QML_DIR, OVERLAY_QML) / 常量 / Qt 路径
    controller/                  30 个文件 / 3834 行，状态和槽（Python）
        controller.py                  Controller 本体：Property + 组合
        jobs.py  window.py  session.py 线程 / 窗口（置顶、对话收起、拖动、尺寸动画）/ 会话
        reading/     tasks deliver scan common mixin      读图、读手册
        monsters/    read icons edit drag mixin                 怪物记录/图标/增删改/拖动、技能统计与介绍（`skillIntro` `setSkillNote`）
        floors/      records items monsters routes grid stairs feedback common mixin
                                                       每层记录/资源行/怪物/路线/格子/楼梯/回执
        status.py  chat.py  battle.py                           人物面板 / 对话 / 伤害计算 + 加属性收益
    toolkit/                      纯函数小工具（不碰窗口）：api desktop（Win32：命中测试/置顶/叫前台）
                                  diagnostics library notes（用户写的技能介绍）pictures state texts
```

---

## 3. 对应关系（views 一份 ↔ controller 一份）

| views 文件夹 | controller 那一份 | 管什么 |
|---|---|---|
| `main_panel/` | `status.py`（`StatusMixin`） | `statusText` `attrText` `itemsText` `goldText` `statusData` `updateStatus` |
| `chat/` | `chat.py`（`ChatMixin`） | `chatLog` `chatReply` `chatting` `errorText`、`sendChat()` |
| `battle_calc/` | `battle.py`（`BattleMixin`） | `battleHero` `battleMonsters` `battleItems`、`computeBattle()` |
| `property_gain/` | `battle.py`（`BattleMixin`） | `propertyGain()`（按层分组的"再加 X 点属性少掉多少血"）+ `_remaining_by_floor()` |
| `map_view/` | `floors/`（`records/grid/stairs`） | `mapHistory` `gridCells` `assignGridCell(s)` `gridPositions` `stairsOf` `saveStair` `clearStair`、`refreshFloorCounts` |
| `route_editor/` | `floors/routes.py`（`RoutesMixin`） | 路线的存/改/删（`saveRoute` `saveRouteCell` `removeRoute`）+ 用地图记录预填 |
| `main_columns/` | `reading/` + `floors/` + `monsters/read.py` | 读取记录 / 每层地图和资源 / 技能统计与介绍（`skillStats` `skillIntro` `setSkillNote`，用户写的介绍存 `logs/skill_notes.json`） |
| `monster_editor/` `icon_picker/` `skill_picker/` | `monsters/` | 怪物记录、图标、增删改、拖动 |

一个概念一个文件（status/chat/battle），十几个函数就一个包——只有这一条判断标准。
`views/MainWindow.qml` 这 3688 行是灰底窗口（`card`）、`flick` 滚动容器、各子界面挂载点
和 `win.*` 状态/函数，**属于主窗口本体**，不再拆。

**机制**：`tools/check_scenarios.py` 把每个场景渲染一遍、抓 QML 运行期警告
（`Unable to assign` / `TypeError` / `is not defined`）——`host.xxx` 没定义、跨文件抓 id
（`mapCard` / `skillBtn` / `flick.width` 这类拆文件漏下的引用）都会在这儿现形；界面确实能点、
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
