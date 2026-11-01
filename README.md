# ChaitaAssistant（拆塔辅助）

盖在魔塔游戏旁边的悬浮层。**只给信息，不给结论** —— 该不该打、先打谁、走哪条路，是你的乐趣，它不插手。

一张卡片装下一整座塔：左中右三栏（地图 / 怪物 / 技能）+ 底部对话框，导航条上挂一扇「伤害计算」小窗。

---

## 它给你什么

| 功能 | 怎么用 | 它给你什么 |
|---|---|---|
| **读地图** | 地图栏的「读取」 | 这一层的截图 + 层号 + 这层有哪些怪（各几只）、有什么资源（血瓶/宝石/钥匙） |
| **读怪物手册** | 怪物栏的「读取」 | 每只怪的生命/攻击/防御/经验 + 技能 + 缩略图（手册数值 × 地图上的只数） |
| **对话** | 底部输入框说一句，回车发出去 | 能聊天、能问事（"这层有什么"），也能顺手纠正读错的数字（"生命是1200"）；说过的话都留着，下一句记得上一句 |
| **伤害计算** | 导航条「⚔」 | 按两座塔自己的引擎公式算：打这只怪掉多少血、连续打一串（怪/宝石/血瓶）最后剩多少，算上技能（破甲/反击/连击…） |
| **地图** | 就在主界面「地图」那一栏 | 左边侧栏快速切层、右边**这一层的大图**（下层压在后面只露一角，切层有动画）；在这张图上画路线、标楼梯、进编辑模式改坐标 |
| **这一层** | 点路线行 / `openFloorSheet` | 这一层的怪、资源、状态、路线、备忘（**清单**，地图在大窗口里）；行首方框勾「打过了/拿过了」，也能自己「＋ 加怪」「＋ 加资源」 |
| **编辑与素材** | 点怪物那一行 / 点怪的头像 / 点「＋ 加技能」 | 改这一行怪的血攻防和技能参数；从素材库挑缩略图；从技能库挑技能 |
| **路线** | 在地图窗口的图上长按 | 自己画一串格子当路线（踩到楼梯会自动换层接着画），记在「这一层」里（只是记录，不规划） |

**不做的事：** 不自动读取、不自动操作游戏、不判断该不该打、不规划路线（路线你自己画，它只记）、不用代码做识别（读图全靠模型，代码只负责裁剪/抠图）。伤害计算只给数字，不给建议。

---

## 支持的两座塔

| 塔 | 引擎 | 窗口进程 |
|---|---|---|
| 教程塔 | RMXP（RGSS Player） | `game.exe` |
| 喵塔 | h5mota（浏览器） | `msedge.exe` |

两塔界面结构不同，各自有一份描述（`chaita/game/towers.py`）。只读**前台**那个游戏窗口：前台不是游戏、或者同时开着两个游戏窗口时会明确提示，不猜。

---

## 装

```powershell
cd C:\Users\87790\dev\ChaitaAssistant
conda env create -f environment.yml
conda activate chaita
```

`environment.yml` 是**唯一的依赖来源**（CI 也吃这一份）：Python 3.12、PySide6、OpenCV、numpy、pywin32、pytest，加上模型调用那两个包
**`agent-framework` + `agent-framework-openai`**（后者单独一个包，漏了它一跑「读取」就 ImportError）。
想自查有没有漏：`python tools/check_deps.py`。

可选：`rembg` + `onnxruntime` —— **只有想让它把图标背景抠干净时才需要**（见下面「图标」）。

---

## 配

项目根目录的 `config.yaml`：

```yaml
api_key: "sk-..."
```

也可以用环境变量 `DEEPSEEK_API_KEY`（优先于文件）。没配的话点「读取」会明确提示缺 key，不会白等。

---

## 用

1. 打开游戏，进到要看的那一页（地图 / 怪物手册）
2. 双击 `拆塔辅助.lnk`（不闪黑框：`.lnk` → `启动.vbs` → `run.py`）
3. **把游戏窗口点到前台**
4. 点对应栏的「读取」
5. 等结果落进面板

| 操作 | 效果 |
|---|---|
| 地图栏「读取」 | 读当前画面：层号 + 这层怪 + 资源，并往「读取记录」里记一条 |
| 怪物栏「读取」 | 读当前手册页：这一页的怪 |
| 导航条「↻」 | 只重读状态行（血/攻/防/魔防/四色钥匙），比整张图重读快得多 |
| 点地图那一栏的层号（侧栏） | 切到那一层（大图跟着换，下面压着的那层只露一角，点那一角也能切） |
| 地图那栏底下的「编辑」/「刷新」 | 进编辑模式（坐标系 + 抓格子改坐标）/ 只用这层的截图重读"有哪些怪、各几只" |
| 导航条「⚔」 | 开伤害计算小窗 |
| 行首方框 | 勾「打过了 / 拿过了」 |
| 「＋ 加怪」/「＋ 加资源」 | 手动加一行（AI 读错时自己补） |
| 「备忘」 | 给这层记一句话（跟着上次记录保存） |
| 点顶栏 / 拖顶栏 / 拖边缘 | 折叠展开 / 移动 / 缩放（无边框窗口，边缘缩放是原生行为） |
| 右上 `✕` 或 `Esc` | 关闭（只有一个实例：再点一次启动器不会叠出第二个） |
| 底部输入框 | 一句话 → 对话；能问事，也能纠正字段 |

主窗口一关，所有小窗一起收掉。地图最多留 **30** 层历史，任务队列最多 **20** 条。

---

## 时间预期（2026-10-26 实测，关掉思考之后；之后新加的功能没重测）

| 动作 | 耗时 | 说明 |
|---|---|---|
| 一次模型往返 | **1.7 ~ 2.3 秒** | 关思考后的基线 |
| 对话 | **3.0 ~ 3.3 秒** | 一次往返 |
| 读怪物手册（一页 5 只怪） | **21 ~ 110 秒** | 取决于模型这一轮调几次 `look`；之后去掉了 sprite 回环，没重测 |
| 读地图（层号+怪+资源） | **32 ~ 80 秒** | 同上 |
| 伤害计算 | **不等** | 本地算公式，一次模型请求都不发 |

`look` 是给模型"放大看清"的工具，每调一次就是一次往返，有硬上限（读手册整页 3 次、读地图 6 次），
防止模型钻牛角尖跑不完。图标不再靠工具回环：模型把每只怪的 icon_box 坐标写进 JSON，代码一次裁完。

---

## 图标与素材库

- 默认：模型在手册页上框出那一格（icon_box 写进 JSON），代码裁下来当图标（**带手册底纹**，因为没抠图）。
- 想干净：把 `u2net.onnx` 放进 `C:\Users\87790\.u2net\`（rembg 的模型，认 `U2NET_HOME`），
  装好 `rembg` 后代码不用改，裁图标时会自动走抠图；没有这个文件就退回纯裁剪 ——
  **没有模型时不会去下载**，所以不会把「读怪物」卡成没反应。
- 素材库 `assets/library/monster/` 只给「点头像换图」用，按名字去顶替手册读到的
  图标意义不大（实测 5 只怪只中 1 只，且 26×25 比模型裁的 157×146 小很多）。

---

## 开发

```powershell
# 全量：单测 + 集成（集成会真开 QML 窗口）
C:\Users\87790\.conda\envs\chaita\python.exe -m pytest tests/

# 只有单测（CI 吃这个）
C:\Users\87790\.conda\envs\chaita\python.exe -m pytest tests/unit
```

- 测试规模：**792 条**（`tests/unit` 663 + `tests/integration` 129）。`unit` 镜像 `chaita/` 的目录结构；`integration` 走真 `Controller` + 真 QML 窗口 + **真鼠标/键盘事件**（只桩外部边界：抓游戏窗口、AI 模型、系统剪贴板）。
  集成测试的判据、允许的豁免、以及"不合格就删"的规矩写在 `tests/integration/README.md`；每条用例的注释都写**测什么**和**交互顺序**（① ② ③）。
- 覆盖率：`python tools/coverage_report.py`（只统计 `chaita/`，别把 `logs/` 里的旧备份算进分母）。
- CI 闸门：`.github/workflows/tests.yml` —— PR 到 `dev`/`main` 时在 `windows-latest` 上**按 `environment.yml` 建环境、只跑 `tests/unit`**。
  集成测试不进 CI：`QT_QPA_PLATFORM=offscreen` 下跑全量会中途访问违例，它只能在本机真窗口上跑。
- 分支：`main` = 发布、`dev` = 开发（功能分支 → PR 到 `dev` → 测试绿 + 人 review → 合；`dev` 稳定后合到 `main`）。
- 写代码/改界面前的约定见 `AGENTS.md`（改界面必须自己看渲染图，交付必须贴实测输出）。

---

## 文件

| 路径 | 作用 |
|---|---|
| `run.py` / `启动.vbs` / `拆塔辅助.lnk` | 启动入口（`.vbs` 是为了不闪黑框） |
| `chaita/ui/views/` | 界面正文：25 个 QML 共 12006 行，**一个界面一个文件夹**。主窗口 `MainWindow.qml`（3397 行）+ 四块（`main_panel` 导航条/抬头/状态行、`main_columns` 三栏、`chat` 底部对话、`map_view` 地图那一栏）+ 各子界面（`floor_sheet` / `battle_calc` / `route_editor` / `monster_editor` / `icon_picker` / `skill_picker`，各自带自己的 `pick_menu`、`edit_card`、`route_layer`、`grid_layer`）+ `shared` 共用件。结构对照见 `docs/UI_MAP.md` |
| `chaita/ui/controller/` | 控制器：`controller.py` 组装 + `jobs` / `session` / `window` / `battle` / `chat` / `status`，读取流程在 `reading/`、怪物行在 `monsters/`、层与路线在 `floors/` |
| `chaita/ui/toolkit/` | 纯函数：`desktop`（光标命中）、`pictures`（截图落盘）、`library`（素材库）、`texts`、`state`（状态文件）、`api`（API key）、`diagnostics`（错误日志） |
| `chaita/ui/startup.py` | 启动与收尾（崩溃日志、渲染后端、`main()`、单实例锁 `logs/app.lock`） |
| `chaita/ui/main.py` · `loader.py` · `qt_env.py` · `constants.py` | 进程入口 / 多文件 QML 加载 / Qt 环境 / 界面常量（路径、节流间隔、上限） |
| `chaita/game/agent/` | 三处要模型的地方：`monster/read.py`（读手册）、`map/read.py`（读地图）、`chat/reply.py`（对话）+ `core.py`（会话）+ `icons.py`（look 工具、裁图标、抠图）；`__init__.py` 一律为空 |
| `chaita/game/read.py` | 读取编排：抓图 → 判画面 → 调 agent → 落成结果 |
| `chaita/game/capture.py` · `winutil.py` · `regions.py` | `PrintWindow` 抓窗口（故意不 import AI，保证点下去先抓到图）/ 窗口与前台判定 / 各塔的界面分块 |
| `chaita/game/battle.py` | 伤害计算引擎：按两座塔的引擎源码核对过的公式算回合与掉血，**纯本地、不发模型请求** |
| `chaita/game/towers.py` · `monster_names.py` · `skillinfo.py` · `iteminfo.py` | 塔描述、怪名归一、技能语义（`assets/skill_effects.json`）、资源语义（`assets/item_effects.json`） |
| `chaita/` 根级：`paths.py` `config.py` `library.py` `library_names.py` `trace.py` | 所有根目录的唯一定义、API key、素材库读写、逐行日志 |
| `assets/` | 图标与素材：`icons/`（状态图标）、`items/`（血瓶宝石）、`library/monster/`（素材库）、`monster_templates.db`、`skill_effects.json`、`item_effects.json` |
| `tests/` | 单测 + 集成测试（`integration/helpers.py` 里记着 7 条踩坑） |
| `environment.yml` · `pytest.ini` · `.github/workflows/tests.yml` | 依赖唯一来源 / pytest 配置 / CI 闸门 |
| `Dockerfile.test` | 隔离界面测试环境（Xvfb 里跑，不碰宿主机鼠标） |
| `tools/` | 一把脚本：`check_deps.py` 自查依赖、`coverage_report.py` 算覆盖率、`_audit_tests.py` 审测试、`_audit_objects.py` 审 QML objectName、`preview_overlay.py` 出渲染图、`verify_all.py` 全量自检 |
| `config.yaml` | API key（已在 `.gitignore`） |
| `logs/`（运行期生成） | `chaita.log` 逐行日志 / `crash.log` 崩溃现场（空 = 没崩）/ `app.lock` 单实例锁 / `last_session.json` 上次的手工记录（只提示不自动恢复）/ `ui_state.json` 窗口位置 |

---

## 已知限制

- 浏览器多个标签时，抓的是**窗口当前显示的那个**，无法指定标签页
- 只支持点按钮读一次，没有自动持续读取
- 读地图给的怪名会受面板里已有名字影响（换来的是两次读同一张图结果一致）
- 画面校验是启发式的（按亮度判断），暗色主题网页可能骗过它
- 地图上怪的小图标只有十几像素，名字本质上是模型在猜；把「读怪物手册」先读一遍，
  名字会准很多（读地图会拿手册里的名字当候选）
- 伤害计算的公式对着两座塔的引擎源码核过，但**只覆盖已实现的那批技能**；没见过的 skill `code` 会明确标成没处理，不会瞎算
- 技能栏是按地图上出现过的怪统计的：地图没读全，技能统计就不全

---

## 怎么工作

```
点「读取」
   ↓  先抓图（PrintWindow，被遮挡也能抓）—— 拿到"点下去那一刻"的画面
判画面：这是地图 还是 怪物手册？
   ↓
地图  → agent.map.read   一个会话里问三句：层号 / 这层有哪些怪 / 有什么资源
手册  → agent.monster.read 一个会话里 look 放大（≤3 次）+ 图标框坐标进 JSON，代码裁/抠
对话  → agent.chat.reply 一次往返：聊天 / 问事 / 顺手改字段，最近 8 轮一起带上
   ↓
落进面板（地图那栏还会把这层存进历史 + 记一条「读取记录」）

点「⚔」
   ↓  读状态行（可选择在窗里再点一次「读取」重读）
battle.py 纯本地按引擎公式算：每只怪一轮一轮走，破甲/反击/连击/吸血算进去
   ↓
每一步的掉血、整串打完剩多少 —— 不改你面板上的任何数据
```

**一张图只上传一次**：同一屏上的几个问题在同一个会话里追问，后面只发文字。

---

## 文档

| 文件 | 内容 |
|---|---|
| `docs/SOFTWARE_DESIGN.md` | 设计说明 + 实测踩坑 |
| `docs/DESIGN.md` | 界面设计（tokens / 组件 / 为什么长这样） |
| `docs/UI_MAP.md` | 哪份 QML 画哪个界面、状态在谁身上、objectName 怎么起 |
| `docs/REDESIGN_NOTES.md` | 逐轮改造记录（含每次实测数据） |
| `docs/TESTING.md` · `docs/ROUTE.md` · `docs/MOTA_GUIDE.md` · `docs/PROGRESS.md` · `docs/PICKER_TODO.md` · `docs/WORKFLOW_MONSTER_NAMING.md` | 测试怎么跑 / 路线功能 / 塔的资料 / 进度 / 待办 / 怪名工作流 |
| `AGENTS.md` | 给接手这个仓库的 AI 的规矩（改动前先给方案、交付必须贴实测） |
