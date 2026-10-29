# 素材库面板 / 怪物编辑浮层 —— 交接（2026-10-27）

两条硬要求的**口径被用户当场更正过**，别照最早那稿做：

- 怪物修改窗口：**居中**（不是"挂在词条下方"——那是 20:33 的稿子，用户 20:39 亲口改的）；
- 点修改窗口里的头像：候选头像**像 QQ 表情包那样贴在头像上方**（不是居中、不是铺满）。

两条都改完并出图、跑过测试了：改在哪见 §二，实测数字见 §四。

## 一、已经改完并在用的（别推翻）

### 素材库选图面板（头像换图）

`chaita/ui/qml/MainWindow.qml`

- `5113` `iconPickerLayer` / `5144` `iconCard`：白底 `#FFFFFF`、`radius 10`、带两层淡投影；
  **不压暗背景**；位置和大小由 `placeIconPicker()` 按头像算（见 §二 B），不再贴窗口底。
- 没有抬头行：第一行就是种族标题 `iconGroupName`，写「种族名 张数」（空三个空格）。
- ~~格子 `iconCellSize = 44`，列数按宽度算（340 宽窗口 = 6 列）~~ → 用户 2026-10-27 晚又说
  "素材库的图片太大了"：**格子 36、一行 6 张（340 宽窗口）**，格子无边框无底色，
  只有「选中那张」和鼠标悬停有淡底。
- 缩略图：`width/height = 原图尺寸 × iconThumbScale`，`iconThumbScale =
  min(1, (36 - 4) / 最大边长)` —— **封顶 1.0，只缩不放**（"不要放大"本来就是红线；
  之前 `min(2, ...)` 会把 36px 的图放到 40px）。当前最大边长 36 → 统一 0.889 倍。
  `iconThumbSmooth` 只在非整数倍时开平滑（整数倍用邻近取样保持像素图清晰）。
- **单个怪不写名字**（用户："单个怪不要名字"）；名字只出现在种族标题上。
- 底部栏：左「搜索」「表情」两个页签（选中的有浅色胶囊底），右「N 张」+ ✕。
- 搜索态：搜索框在面板**顶部**（放大镜 + 占位「搜索表情」），网格从 `y = 48` 开始；
  点「表情」清空搜索回列表。

`chaita/ui/controller/monsters.py`

- 新增 `monsterIconMaxSide()`：返回素材库里最大一张图的边长（`library.pictures("monster")`
  的 `width/height` 取大）。界面拿它算统一缩放倍数，别在 QML 里写死。

`tools/preview_overlay.py`

- `iconsearch` 场景补了 `window.setProperty("iconSearchMode", True)`，否则搜索框不出现，
  截出来的图看不出搜索态。

### 测试跟着改了（都过了）

- `tests/test_integration.py`：两个素材库用例按「格子不写字、标题带张数」重写；
  新增 `test_icon_thumbnails_keep_one_scale_and_are_never_cut` —— 逐张读原图尺寸，
  断言第一张到第 N 张用的是**同一个倍数**，且每张图的宽高都 ≤ 格子（不许被切）。
- `tools/test_ui_synthetic.py`：素材库一段改成「点『搜索』页签才出现搜索框」，
  搜索/别名（石头怪 → 石怪）改用 Python 侧同样的匹配规则验。

## 二、这次做完的两件事（2026-10-27 晚，按用户更正的口径）

### A. 怪物修改窗口：居中 + 能拖

`chaita/ui/qml/MainWindow.qml`

- `4509` `monDialog`：只留一层"点外面关掉"的全窗 `MouseArea`，**0.32 的黑遮罩删了**
  （弹层不压暗是红线）。
- `4521` `monCard`：`cardW = min(300, 窗口宽 - 16)`、`cardMaxH = max(160, 窗口高 - 16)`；
  `x/y` 都是"先居中、再夹回窗口（最少留 8）"；`bodyMax` 改成按 `cardMaxH` 算
  （扣抬头 50 + 底部按钮 44）。
- 行点击那条链**没动**：居中不需要行的坐标，`openMonster(index)` 保持原样 ——
  旧稿要的 `mapToItem` 传 x/y 因此作废。
- 用户："怎么不能移动" → 卡片背景那个"吞点击"的 `MouseArea` 改成拖动把手
  （`monCardGrip`，`objectName: "monCardGrip"`）：按住卡片空白处拖（走 6px 才算拖，
  点一下不飘），位移用 `mapToItem(monDialog, ...)` 算窗口坐标的差值（卡片一动
  `mouse.x` 会跟着变，直接用会抖），每次夹回窗口；拖过的位置记在 `monCardX/Y`，
  这次运行内不再回居中（`-1` 才是"居中"）。光标给 `OpenHand/ClosedHand` 当提示。
- 卡片宽度 300、窗口 340 时左右只剩 20px 可挪 —— 想挪远先把窗口拉宽。

### B. 头像候选面板：贴在头像上方（QQ 表情包）

- 根上加 `iconMenuX/Y/W/H`（在 `iconSearchMode` 后面）+ `onIconPickerChanged:
  Qt.callLater(placeIconPicker)`：预览/测试直接置 `iconPicker` 也会摆对位置，
  `openIconPicker()` 不再自己算。
- `placeIconPicker()`（挨着 `openIconPicker`）：宽 `min(280, 窗口宽 - 16)`；用
  `monIconBox.mapToItem(iconPickerLayer, 0, 0)` 量头像位置，面板底边贴头像上方 8px；
  **上方不够 200 就翻到下方**；高 `min(330, 那边可用空间)`、最少 120；四边都夹回窗口。
- `5193` `iconCard` 只照抄 `iconMenuX/Y/W/H`：不再 `width: bodyW`、不再贴窗口底。
- 面板内部（种族标题带张数、底部搜索/表情页签、搜索态）没动；**格子 44 → 36、倍数
  封顶 1.0**（用户："图片太大了"，见 §一）。
- 窗口缩放 → 面板直接关掉（`closeIconPickerIfOpen()` 挂在已有的 `onWidthChanged` /
  `onHeightChanged` 里，用户拍板"直接关掉"）。编辑卡片本身居中，缩放会自己重新居中、
  不关（关掉会丢用户正在输的字）。

新增用例（`tests/test_integration.py` → `SubViewTest`）：

- `test_monster_editor_card_is_centered`
- `test_monster_editor_card_can_be_dragged`（`drag_item` 新增 `from_point=`，
  默认还是按正中；卡片要按左侧内边距那条空白）
- `test_icon_picker_floats_above_the_avatar`
- `test_icon_picker_flips_below_when_the_space_above_is_too_small`
- `test_icon_picker_closes_when_the_window_is_resized`
- `test_icon_thumbnails_keep_one_scale_and_are_never_cut` 加了"只缩不放 + 格子 ≤36"

## 三、验证命令（改完照这个跑）

```powershell
# 出图看位置（第 2 个参数才是输出路径，第 3 个是宽度，第 4 个是场景名）
C:\Users\87790\.conda\envs\chaita\python.exe tools\preview_overlay.py docs\capture\iconpick.png 340 iconpick
C:\Users\87790\.conda\envs\chaita\python.exe tools\preview_overlay.py docs\capture\monedit.png 340 monedit
# 场景自检（QML 运行期告警 + 尺寸）
C:\Users\87790\.conda\envs\chaita\python.exe tools\check_scenarios.py iconpick iconsearch monedit
# 素材库相关用例
C:\Users\87790\.conda\envs\chaita\python.exe -m unittest tests.test_integration -k icon
# 全量
C:\Users\87790\.conda\envs\chaita\python.exe -m unittest discover -s tests
```

## 四、测试现状（2026-10-27 23:0x 跑的）

- 全量：`Ran 681 tests in 266.822s` → **`OK`**（用户："测试的问题也修了"）。
  地图小窗/缩略图那一轮的改动见 `docs/REDESIGN_NOTES.md` §33。
  之前那两条红的是这么修的：
  - `test_singleton_kinds_are_folded_into_other` → 改名成
    `test_a_kind_with_one_picture_keeps_its_own_name`：**旧规则作废**。`library.pictures()`
    里写着"用户：现在界面和文件顺序保持一致 —— 不再把单只的族并进「其他」"，用例还按旧
    规则要「勇者」折进「其他」，是**用例过时**，不是数据错（数据是用户逐张核对过的，
    不能为了变绿去动）。
  - `test_no_two_templates_look_the_same` → 新增 `tools/fix_template_icons.py`，按
    `(塔, 贴图键)` 把 DB 里 62 条失效的 icon 重新指回现有文件（`library/monster/xxx.png`，
    相对 `assets/`，别再写 `assets/` 前缀 —— 读库那边已经拼了）。
    **没重建模板库**（重建 = 编号重排 = 用户重看一遍）。备份：`logs/monster_templates_before_fix_icons.db`。
- `tools/test_ui_synthetic.py`：**`==== 结果：全部通过 ====`**（215 项 PASS，exit 0）。
  之前红的三项都出在自检工具自己身上：
  - `_sprite()` 写死了老的素材文件名（`fairy_dark_sprite.png`），素材库重排后返回 `""`
    → 怪行/编辑界面的缩略图检查红。现在按 `_英文名` 后缀找，编号变了也不受影响。
  - 「并掉的重复名字还能搜到」的断言反了：现在条目名是「石头怪」，旧名「石怪」在
    `names` 里当别名 → 改成搜「石怪」应命中「石头怪」。
- `tools/check_scenarios.py`：`monedit` / `iconpick` / `iconsearch` 三个场景 `OK`、
  `warnings=0`、逻辑高 657（出图 510×986）；全量场景也跑了一遍，没有 `BAD`。
- `tests.test_integration -k icon`：10 个 `OK`。
- **一次偶发**：同一套全量在 21:35 那一轮只跑了 125 秒、`BattleTest.test_deleting_a_row_and_clearing`
  点到隔壁行（删错了行）；重跑 496 秒全绿。单跑 `BattleTest`（16 条）、单跑整个
  `tests.test_integration`（100 条）都过。跟这次改的两层无关，但说明**全量跑起来有
  环境相关的抖动**，见到单条红先重跑一次再判。

## 五、红线（别碰）

- 素材库文件名/编号、`assets/library/manifest.json`、素材库显示顺序：用户逐张核对过，
  一重建编号就整体重排，等于让他重看一遍。
- `tests/` 里跟素材库无关的用例、构建产物、阈值，不要为了"变绿"去改。
- 弹层一律不做全屏、不压暗、不居中铺满。
