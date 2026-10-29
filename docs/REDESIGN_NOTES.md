# 界面重设计交接（每层交互 UI）

> **2026-10-26 续记：这份文档描述的是"本层为主角"那一版，已被 v12「塔级总览」取代。**
> 现行设计见 `docs/DESIGN.md`；界面实现是 `chaita/ui/qml/MainWindow.qml`；
> 旧界面存档 `logs/backup/overlay_20261026_dark_r15.qml`。
> 下面这些历史记录留着是因为"为什么迭代了十几版"的过程还有参考价值，
> 但里面的测试项数（256 项 / 27 场景 / 340 tests）都是当时的数，别拿来当现状。

> 目标：**完全重新设计每一层的交互 UI，务必简洁美观，最重要的是合理**
> 这份文档给"下一个会话/下一个 AI"接手用：现状、已完成、剩余、怎么验证、怎么回退。

---

## 1. 当前状态（2026-10-22 收尾）

- 单元/集成测试：`340 个全过`（命令见 §5）
- 界面自检：`tools/test_ui_synthetic.py` `256 项全过`（本层行内编辑 / 选怪直接加 / 选资源直接加 / 本层待办勾选 / 技能效果与数值 / 怪物参数弹窗 / 状态区 / 记录 / 折叠态 / 顶栏闪光 / 上次记录 / Esc / 失败路径）
- 渲染体检：`tools/check_scenarios.py` 把 `preview_overlay.py` 的 **27 个场景**
  各渲染一遍，抓 QML 运行期警告（`Unable to assign` / `TypeError` / `is not defined`
  / `Binding loop`）并检查不是空图，最后一行要是「结果: 全部干净」
  （图在 `logs/_scenarios/`，可以逐张看）
- 界面文案体检：`tools/dump_ui_text.py` 列出所有"给人看的中文文案"（现在是 37 条，全是按钮/字段名/占位符）
- 纠错链路已在真实窗口上验证：`tools/verify_correction_live.py`（读一次 + 连发两条指正，检查"改对、上一轮不被改回去、没提到的字段不动、reply 非空"）

- QML 正常加载、界面能正常渲染（改完必须截图确认，空白截图 = 改坏了）
- 备份文件：`logs/overlay_before_*.py`（每次大改前都会存一份，回退用；
  第二轮开工前是 `logs/overlay_before_mapflat.py`，第三轮开工前是 `logs/overlay_before_rows.py`）
- 代码里 QML 在 `chaita/ui/qml/MainWindow.qml`（2026-10-26 之前塞在
  `chaita/ui/main.py` 的 `OVERLAY_QML` 三引号字符串里；拆目录的经过见第 9 节）

## 1.5 定调（2026-10-22 晚，owner 亲口纠正，后续一律照这个）

- **先是信息，不是判断。** owner 原话：「是信息」「我不需要你一个辅助工具替我玩游戏，决策是给玩家获取乐趣的」。
  所以：面板只摆**事实**（这层有什么、这只怪多少血/攻/防/经验、有什么特殊、道具什么效果、截图长什么样），
  **不摆结论**——不做掉血计算、不显示"能不能过/险不险"、不排序"强弱"、不给"先打谁"的建议。
- **不藏信息。** 试过一版把内容分成「本层 / 怪物 / 技能 / 记录」四个分段标签（一页一次只看一段），
  owner 判定比之前更差（原话"现在就是依托屎"）——**已整体回退**成一屏流（现在这版）。
  那次带标签的版本存在 `logs/overlay_with_tabs.py`，只作记录，别再拿回来。
- **一屏流 = 五段纵排**：状态 → 怪物 → 地图 → 技能 → 读取记录，全都在同一屏里滚，
  靠字号/颜色/间距分层，不靠折叠和切页。
- 按这条做的两处（本轮）：
  1. **怪物行就地显示它的技能**（`先攻 · 纳魔为攻 30%` 这种），不用再跑到"技能"区反查。
     见 `monSkillsText()/monSkillParts()` + 怪物行第三段。
  2. **数值一个都不能被截掉**：以前长数值会被省略号吃掉（截图里 `经验 …`），
     现在改成 `Flow` 一段一段排——「生命 21000万 · 攻 6100万 · 防 3500万 · 经验 500」
     放不下就整段换行，不会出现「经验」在行尾、数字掉下一行这种断词。
     见 `monsterStatParts()` + 怪物行 `monStatFlow`。
  3. **状态区把「等级 / 经验 / 升级还需」各摆各的**：以前只有一个 `⇄` 在"经验 / 升级还需"
     之间切，而且显示的数永远是 `next` —— 一个小数字被叫两个名字；真正读到的「等级」
     从头到尾没显示过。现在读到什么就摆什么、各带各的标签（`等级 12  经验 3400  升级还需 12000`），
     `⇄` 和 `expToNext` 一起删掉。
  4. **读取记录补上"什么时候读的"**：数据里每条任务都有 `started`，以前只在"进行中"
     用它算已用秒数，读完就把时间丢了。现在完成/取消的行右侧有 `22:06` 这种时间戳
     （失败行右边是「重试」按钮，不挤时间）。
  5. **当前层那一行直接摊开"还没打/拿"的名单**：以前只有 `4 怪 · 4 资源 · 剩 8`，
     具体是哪几只、哪几样要点开弹窗。现在你正站着的那层（标题栏层数对上）在行下面
     列一行 `还没打/拿：监狱守卫 ×6 · 血蚁 ×3 · …`，勾掉一项它就消失；
     全清掉就不占行高（`· 清了`）。其它层保持 28 高，点开看全部。
     见 `floorLeftParts()` + 地图行 `leftLine`（`objectName: "mapLeftLine"`）。
  6. **分段间距**：段与段之间加 6px，头 + 卡片还是一组，组与组之间透气。
     ~~空的分区不摆标题~~ —— 这条后来被 owner 否了（「我的技能栏呢？没有就不显示
     用户怎么知道有这个功能？」）：技能 / 读取记录两栏**标题常驻**，空的时候在标题下
     各给一句说明（"地图上加过怪之后，它们的技能会汇总到这里" / "每次点「读取」都会记在
     这里（含截图和时间）"）。只有"整屏全空"时不再逐段解释，由顶部那句总引导负责。
  7. **窄窗口顶栏不再压住 ✕**：实测 300px 宽截图里塔名会盖到关闭按钮上。
     现在塔名 `Layout.fillWidth` + 右对齐 + 省略号，窗口 < 240 时软件名和折叠箭头一起让位，
     保住「读取」和塔名。回归测试：`窄窗口下塔名不压到关闭按钮`（窗口拉到 200 逻辑宽量坐标）。
  8. **跨层找东西（"更好查"）**：地图标题右侧加了「搜」幽灵按钮（不点开不占地方）。
     点开是一个输入框，按 **层号 / 怪名 / 资源名** 过滤已记录的层；标题上的计数变成
     `命中/总数`（例如 `1/2`）；哪层都没命中就直接写「记录里没有哪层带「X」」，
     不摆空卡片；收起时自动清词。跨层问"蓝宝石在哪几层"不用再一层层点。
     见 `mapFiltered()` + `mapSearchOpen/mapQuery` + `objectName: "mapSearch"`。
     预览：`preview_overlay.py out.png 900 search`。
     **2026-10-25 已整块删除**（owner：「把地图的搜删掉吧」）：搜索按钮、输入框、
     命中计数、`mapFiltered()`、`mapSearchOpen/mapQuery` 全没了，地图列表直接绑
     `controller.mapHistory`；`syncMapView()` 改用全量列表。预览场景 `search` 也从
     `preview_overlay.py` / `check_scenarios.py` 里删掉（旧截图
     `logs/_scenarios/search.png` 留着当历史）。回归测试：
     `地图标题里没有「搜」按钮`。
  9. **长技能名不再盖住数量**：技能行名字最多占行的 52%，再长就省略号
     （`超长技能名字用来测试省略…` + 右边还是完整的 `×1`）；以前名字一长就顶到
     「数值 / ×N」上，两段字叠在一起。回归测试：`长技能名不压到数量`
     （量名字右边缘 vs 数量左边缘）；预览：`preview_overlay.py out.png 900 longskill`。
  10. **压力场景体检**（`preview_overlay.py out.png 712 stress`：大数字 / 长名字 / 7 个技能）
      发现并修的两处：
      - **技能卡把最后一行切成半截**：不点开时高度封在 140，7 个技能装不下，
        最后一行只露出上半截。现在跟着实际行数走、上限 260。回归测试：
        `最后一行技能没被卡片切掉`（量最后一行底边 vs 卡片底边）。
      - **层名自己带空格时认不出"当前层"**：以前拿顶栏标题的"最后一段"去比，
        `封印之地 3层` 这种层名永远对不上，当前层的 ● 和"还没打/拿"名单都不出现。
        现在按「等于」或「以 `空格+层名` 结尾」判断。回归测试：`层名带空格也能认出当前层`。
  11. **三张卡片的高度上限对齐"整行 + 内边距"**（`stress2` 场景：一层 14 怪 12 资源 + 10 条记录）：
      记录卡 140 → **148**（= 8 + 5×28），地图卡 264 → **260**（= 8 + 9×28），
      技能卡 260 → **250**（= 8 + 11×22）。以前上限不是整行，最后一行总被切掉半截。
      回归测试：`记录卡高度是整行（3 条 = 92）`、`记录卡最多显示整 5 行（148）`。
  12. **「这一层」弹窗的滚动区也按整行取高度**（`stress3` 场景：一层 20 怪）：
      以前高度是 `卡片高 - y - 52` 这种任意值，底部那行只露出上半截
      （「怪10号」和它的数量框被切）。现在：内容放得下就按内容给；
      放不下取 `20 + 24×k`（20 = 「怪」标题 18 + 间距 2，24 = 行高 22 + 间距 2）。
      注意**只在内容超出时才取整** —— 一开始无条件取整，小弹窗反而把资源行挤出
      可视区，被 `资源也能勾拿过了` 这条测试抓到。
      回归测试：`滚动区高度对齐整行`、`没有一行被切成半截`（扫一遍所有本层怪行，
      量有没有一行横跨滚动区边界）；预览：`preview_overlay.py out.png 760 stress3`。
  13. **放不下时用悬停看全**（`stress5`：资源名 + 长效果）：本层弹窗里资源名只有 50px、
      效果吃掉剩下宽度，长了就省略号 —— 以前被省略的部分**再也看不到**。
      现在名字/效果/本层怪名被省略时，鼠标停上去 450ms 弹出完整内容
      （只在 `truncated` 为真时才弹，没省略不打扰）。
      回归测试：`短效果不标省略、长效果标了`（`truncated == [False, True]`）。
  14. **怪物编辑弹窗扛得住极端值**（`stress4`：名字 15 字 + 生命 12 位）：
      名字框、生命/攻击/防御/经验、技能行、保存/删除/取消都没有溢出 —— 这一处没改代码，
      只是加进场景清单常驻体检。
  15. **截图工具链的两个坑（这轮才挖出来，之前的截图可能是错的）**：
      - `preview_overlay.py` 每跑一次都会在退出时把窗口尺寸写进 `logs/ui_state.json`，
        下一次启动又按它恢复 —— 于是同一个场景有时 900 高、有时 712 高，
        甚至整块内容没来得及画（`map-done` / `chat` / `mon-drag` 实际渲染成了空面板，
        但旧检查只按文件大小判断，19KB 也判"OK"）。现在：加环境变量 `CHAITA_NO_UI_STATE`，
        `preview_overlay.py` 和 `test_ui_synthetic.py` 自己设置它 —— 截图/自检不再读写
        用户窗口状态。
      - `check_scenarios.py` 以前不删旧图：渲染进程崩了（这次是我把 preview 改出了
        缩进错误）就拿着上一次的图当这一次的结果。现在先删旧图、检查进程退出码、
        并**校验图片尺寸**（按 340 逻辑宽换算出期望高，折叠场景豁免）。
      - 顺带：`_apply_height` 设两次（900ms / 1600ms），避开启动时那次"展开动画"
        把尺寸拉回 `savedHeight`。
  16. **字号全部走 `theme` 令牌**：QML 里原来有 44 处硬编码 `font.pixelSize: 9/10/11/12`，
      和 70 处令牌混着用（同一个 10px 标签有的走令牌、有的写死，以后调字号必漏）。
      现在只剩两处刻意的原值：`8`（当前层小圆点）和 `15`（弹窗标题）。
      `9` 与 `10` 都收敛到 `theme.fontLabel`(10)、`11` → `fontMeta`、`12` → `fontRow`。
      验证：`unittest 340 OK`、`test_ui_synthetic 256 项全过`、
      `check_scenarios` 31 个场景全干净、`audit_alignment` 超出网格 0 条。
  17. **场景体检失败自动重跑一次**：偶发的"这一帧还没画出来"会被当成界面坏了
      （`stress3` 在连续扫 31 个场景时遇到过一次，单独跑却是好的）。
      现在 `check_scenarios.py` 先删旧图 → 渲染 → 判失败 → 再渲染一次 → 才报 BAD。
  18. **读到新的一层，自动把「当前层」滚进视野**：玩家翻着上面几层看，回游戏走一步再点「读取」，
      新层插在最上面，但列表还停在原来滚到的位置，当前层（●）在屏幕外，得自己往上滑。
      现在 `syncMapView()` 在**当前层名字变了**的时候把它 `positionViewAtIndex(i, Contain)`；
      只是勾选/改数量（层没变）不滚，不跟用户的手抢。
      回归测试：`当前层自动滚进视野`（造 15 层、当前层设成第 12 层，量 `mapList.contentY = 84`）。
  19. **读取记录不再挂绿勾**（owner：「你那绿勾莫名其妙谁软件这么设计了？」）：
      一列绿勾没有信息量 —— "读成功"本来就是常态，而且 ✓ 在这里很容易被读成
      "这层清了"（游戏语境里 ✓ 是"打过/拿过"）。现在只有需要你看一眼的才画图标：
      失败红 `✕` / 进行中 `…` / 取消暗色 `⊘`；成功什么都不画，行里只留缩略图 + 层名 + 时间。
      本层弹窗里的标记也一并换了：**打过了/拿过了 = 实心点 `●`（brand 色），没打过 = 空心 `○`**，
      保存回执改成"那一格的底色闪一下"，完成按钮闪成「已保存」—— 全界面不再有 ✓。
      回归测试：`记录只给失败和进行中画图标`、`取消的行用 ⊘，全程没有 ✓`。
  19b. **勾号全删 + 「这一层」两段列宽对齐**（owner：「把你的狗屎勾号删了」
      「最基本的对齐都做不到吗」）：
      - 打过了/拿过了：`✓/○` → **`●/○`**（实心点用 brand 色）；
      - 每行"已存"回执：不再挂 `✓`，改成**那一格的底色闪一下**（`monSavedFlash` / `itemSavedFlash`）；
      - 完成按钮：`✓ 已保存` → 「已保存」；
      - 列对齐：怪那段是 勾14/图18/名字 W-116/数量34/✓12/✕18，资源那段是 勾14/图20/名字50/
        效果 W-202/数量34/✓12/✕16 —— 两段的「数量」「✕」根本不在一条竖线上。现在统一成
        勾14/图18/…/数量34/✕18，怪名字 = W-100、资源效果 = W-154；
      - 记录行右侧时间从 8px 收到 4px，四段的右边缘现在都落在渲染像素 482（实测量过）。
  19c. **资源效果可以改了**（owner：「为什么改不了蓝宝石加的数值？」）：
      之前把效果做成只读，是误解了"效果还让我填"那句 —— 那是"别让我手打"，不是"不许改"。
      现在：默认值仍由道具表填好；用户改过的值打 `effect_manual` 标记，显示层不再拿表覆盖；
      清空则退回跟表走。QML 里效果从只读 Text 变成输入框（聚焦时出底色）。
      回归测试：`test_effect_falls_back_to_table_when_cleared`（单测）、
      `手改的效果写回数据`、`手改后显示层不再被道具表覆盖`（界面）。
  19d. **顺手修了行内输入框的两个坑**：
      - 输入框失焦也会触发 `onEditingFinished` → 值没变也白存一次 → 整行重建把别处
        正在抢的焦点打断。现在三个行内输入框（怪数量 / 资源数量 / 资源效果）都先比较值，
        没变就不落库。
      - 「加完资源光标落在数量框」原来在行建好时就把 `floorItemCountFocus` 清成 -1，
        一旦这一行随后被重建就永远抢不到焦点。现在延时 800ms 才清，重建出来的行会再试一次。
        回归测试：`点「加资源」后光标在数量框`（失败信息会打出当前焦点是谁）。
  19f. **"这个值可以改"要怎么表示**（owner：「查查别人是怎么表示一个值可以给用户改的」）：
      查了两份公开规范 —— Ant Design「Make it Direct」（三态：浏览/悬停背光+提示/点开变输入框
      带确认+取消）和 AWS Cloudscape「Inline edit」（**永远给出可编辑的视觉提示**、编辑时值变输入框
      并出现确认/取消、提交后给成功反馈、允许保存或放弃）。
      落地：数量格/效果格**常驻浅底**（看得出是格子）→ 悬停提亮 → 聚焦加 brand 描边；
      Enter 提交、**Esc 撤销回原值且不关弹窗**、提交后那一格闪一下。
      回归测试：`可改的效果格看得出是格子（有底色）`、`Esc 撤销这一格的修改`、`Esc 撤销时弹窗还开着`。
  19h. **「读地图」真的只读地图了**（owner：「为什么地图不可以单独读取？」）：
      以前它走通用的 `game_read.read()`：会**再读一遍人物状态**并覆盖状态面板
      （生命/钥匙都可能被这次读取改掉），却又不读这一层的资源。
      现在只做两件事：`read_floor`（层数）+ `map_snapshot`（截图），**不调用 read()**；
      交付时 `_deliver(mode="map")` 只更新"我在哪"（顶栏层数），人物面板一个字段都不动。
      顺带修：`_store_map_entry` 以前会拿"这次读到的（空的）怪/资源"覆盖那层已有记录 ——
      按一次「读地图」就清空；现在只有真的读到内容才覆盖。
      回归测试：`test_map_mode_does_not_touch_person_panel`、`test_map_mode_keeps_existing_rows`、
      `test_read_map_creates_floor`（断言走 read_floor、不调 read）。
  19i. **底部 AI 区：默认展开 + 去掉方角**（owner：「底部ai对话框凸出来的问题还是没解决」
      「为什么又隐藏AI对话框」）：
      - 聊天条以前是一块**铺满窗口底部的矩形**：同色时看不出，压在游戏画面上时
        它的方角会把卡片圆角盖掉 —— 看起来就是"底部凸出来一块"。现在底色透明，
        背景交给外层卡片，圆角保住。
      - 以前默认收起、只留一行"发现读错了？点这里直接说"，等于把功能藏起来；现在
        **默认展开**（输入框 + 发送一直在），点「收起」才收回一行，再点那行又展开。
      回归测试：`输入区默认展开（不是一行提示）`、`聊天区底部留了内边距（不贴边）`
      （量 gap=12）、`聊天条背景是透明的（方角不许盖住卡片圆角）`、`再点一下重新展开`。
  19j. **选完技能别再跳回顶部**（owner：「为什么我选一个技能直接跳最上面了？」）：
      `pickSkill()` 里原来顺手把 `skillQuery` 和搜索框清空 —— 过滤条件一没，
      候选列表立刻变回整本技能目录并滚回顶部，刚点的那一行就"跳走"了。
      现在保留搜索词和列表位置，可以连着加下一个；要清空按 Esc（搜索框本来就有）。
      回归测试：`加完技能后搜索词还在（列表没跳回顶部）`、`列表仍然是过滤后的`
      （后者只看 `skillList` 那一块，因为已加的技能行里也有同名文字）。
  19g. **Esc 让位给正在编辑的格子**：全局 `Shortcut{ Esc }` 优先级高于输入框的
      `Keys.onEscapePressed`，格子里按 Esc 会把弹窗关掉。现在窗口记 `editingField`
      （引用比较，避免两格切换时计数错乱），快捷键在它非空时让位；再按一次 Esc 才关弹窗。
  19e. **技能栏/记录栏不再"空就消失"**（owner：「我的技能栏呢？没有就不显示用户
      怎么知道有这个功能？」）：标题和计数常驻，空的时候各给一句说明；
      只有整屏全空时才交给顶部那句总引导。回归测试：
      `空面板也看得到「技能」这一栏`、`空面板也看得到「读取记录」这一栏`、
      `空面板四个分区标题都在`；预览：`preview_overlay.py out.png 760 noskill`。
  20. **又清掉两处"没有信息量"的东西**（接着 owner 对绿勾的意见一起看）：
      - **地图每行前面的 `▸`**：它暗示"展开"，实际是打开弹窗；当前层那行会变成
        `▸ ● 地下30`，两个符号挤在名字前。删掉箭头，只留 `●` 表示"你在这层"。
        顺带把 `●` 改成固定占 8px：以前只有当前行有圆点，导致层名比别的行右移、
        一列层名对不齐。
      - **顶栏「读取」按钮不再改文案**：以前点下去按钮自己变成「读取中…」，
        而按钮右边另有一行「读取中…」在报同一件事 —— 头 1.2 秒出现两个"读取中…"，
        而且按钮标签跳变会让布局抖一下。现在按钮永远是「读取」（仍会闪绿），
        进度只由右边那行负责。
  21. **截图被拍成"默认 712 高 / 空面板"的真根因**：窗口的 `width/height` 绑在
      QML 的 `expandedWidth/expandedHeight` 上，而启动时会先 `collapsed=true` 再展开
      （`animateSize` 动画到 `savedWidth/Height`）。`preview_overlay.py` 只设
      `width/height`，就会被动画拉回去；冷启动 QML 编译慢时，2200ms 抓图正好落在
      这中间 —— 于是同一场景有时 900 高、有时 712 高，甚至内容还没画（`map-done` 19KB）。
      现在：三个源头一起设（`expanded*` / `saved*` / `width,height`），并且**轮询等尺寸
      到位**再等 400ms 抓图（最多 12 次 × 300ms）；`check_scenarios` 校验图片尺寸兜底。
   22. **启动慢的真根因：界面为了查一张图标把整条 AI 链拖进来了**（owner：「感觉现在
      软件的开启速度要慢很多你有头绪吗？」）。实测（`tools/startup_regression.py`，
      改版前快照 vs 现在，各 2 次）：
      - 改版前（QML 2308 行）：`loadData` 532/570 ms，到首帧 647/686 ms；
      - 修之前（QML 5140 行）：`loadData` 2190 ms，到首帧 2360 ms（冷盘时 6.9 s）；
      - `cProfile` 抓 `QQmlComponent.create()`：**2245 ms 里 2026 ms 是
        `itemChoices()` 触发的 import**（`chaita.game.read` → `agent_read` →
        `agent_framework.openai` → `openai`，1.4 s，外加 cv2/numpy 0.6 s）。
      - 为什么会这样：`itemChoices()` / `_get_map_history()` 只为了查"这张图标文件
        在不在、叫什么"而 `from ..game import read`，而 `read.py` 顶上就带着
        cv2/numpy 和整条 AI 链；这两个又都在**启动时**求值（「＋ 加资源」的下拉
        模型和地图列表）。第二次 `create()` 只要 45 ms，所以不是"界面太大画得慢"，
        是**每次启动白付一次重模块 import**。
      - 修法：图标规则（`items_dir/icon_exists/icon_map/icon_for/save_icon_map`）
        搬进轻量的 `chaita/game/iteminfo.py`，`read.py` 保留同名函数做转发（老调用点
        和测试不用改语义）；`overlay.py` 里那 12 处 `game_read.*` 换成 `iteminfo.*`，
        UI 路径不再 import `read`。
      - 结果：`create()` 2245 → **417 ms**（Python 侧只剩 5 ms）；到首帧
        2360 → **943-948 ms**（3 次），和改版前 651-654 ms 的差距只剩 QML 变大的部分。
        回归测试：`Ran 344 tests ... OK`、`_synthetic.log` 268 项全通过、
        `check_scenarios.py` 32 场景全部干净、`smoke_close.py 6` 退出码 0。
   23. **owner 一口气提的 5 条（2026-10-25 晚，截图圈了怪物行右端和地图行右端）**：
       - **两个「清空」按钮删掉**（怪物区、地图区各一个）：这两个按钮是"全清"，
         读错一层时用户想删的只是那一层（所以有了下面第 2 条的每行删除）。
         顺带把「＋ 加怪」改成靠「读怪物」定位 —— 以前按"怪物多不多"写死右边距，
         少了「清空」那个数字就没意义了。
       - **怪物每行末尾一个删除按钮，只有图标没有文字**（`objectName: "monDel"`，
         一个 ✕，悬停变红底）。声明在整行 MouseArea 之后 = 盖在它上面：点它不会
         顺带打开编辑弹窗，也不会开始拖动排序。数量胶囊相应左移 22px，
         正文宽度从 `-46` 收到 `-68`，长名字不会压到按钮上。
       - **地图每一层一个刷新按钮（↻）**：点它统计**这一层已经添加的怪**在这层
         地图截图里各有多少只（`Controller.refreshFloorCounts` →
         `_start_count_task` → `read.read_monster_counts`）。三种情况都说清楚：
         这层没加怪 →「统计失败：这层还没加怪」；没截图 →「统计失败：先点
         「读地图」拿截图」；统计中那行的 ↻ 变成「…」（`Controller.countingFloor`）。
         **重读数量不再按名字重排**：顺序是用户拖出来的，`_apply_counts` 只改数字
         （原来那句 `mons.sort(...)` 会让拖好的顺序被打乱）。
       - **「全属性提升」换成每项属性的具体数值**：黄宝石在塔里的 tip 只写「全属性
         提升」，等于什么都没说。`tools/build_item_effects.py` 加了 `expand_attrs()`，
         从 `itemEffect` 语句（`core.status.hero.atk += 6`）里逐项算出来，重新生成
         `assets/item_effects.json`：黄宝石 = **生命 +1000 · 攻击 +6 · 防御 +6 ·
         魔防 +10**（只变了这一条，alt 值都保留）。加资源下拉改成"名字一行、效果
         一行"（原来挤一行，长效果会压到图标上）；资源行里的效果格子失焦后把光标
         退回开头，长效果从「生命」开始显示，而不是只剩尾巴。
       - **地图每一层可以写一句备忘**：行右端「备忘」入口 → 行内出现输入框
         （回车保存 / Esc 取消 / 失焦保存）→ 存进 `_map_history[i]["memo"]`，
         有备忘时那一层下面常驻一行「备忘：…」（长的话省略，悬停看全文）。
         备忘跟着 `logs/last_session.json` 一起走（点「恢复」能带回来）。
         Esc 归这个输入框：窗口级 `Shortcut{ Esc }` 在 `win.memoEditFloor` 非空时
         让位，不然按 Esc 会把窗口关掉。
       - 回归测试：`Ran 349 tests ... OK`；`tools/test_ui_synthetic.py` 重建后
         60 项全部通过（含删除按钮、备忘、刷新、无截图提示）；`check_scenarios.py`
         32 场景全部干净；`smoke_close.py 6` 退出码 0、`crash.log` 0。
       - **事故记录**：改 `tools/test_ui_synthetic.py` 时用了
         `(Get-Content -Raw) -replace ... | Set-Content -Encoding utf8`，
         Windows PowerShell 按 GBK 读进、UTF-8 写出，把 2157 行里的中文和换行写坏了
         （坏版本留在 `logs/test_ui_synthetic_broken.py`）。后来按 §1.5 记的检查项
         重建了这份自检脚本（57→60 项），覆盖范围写在文件头的 docstring 里。
         教训：**这个仓库的中文文件不许用 PowerShell 的 Get-Content/Set-Content
         来回捣**，改代码只用编辑工具或 Python（显式 utf-8）。
   24. **读怪物只动"怪物"那一栏**（owner：「这个功能现在不是刷新做的吗？」→
       「不要回填！！！你拿我的话当放屁吗」）：
       `_deliver_monsters()` 以前读完手册会 (a) 把那一层的怪列表整段替换成手册的怪
       （按名字重排），(b) 再自动发一次"数这一层各有几只"；`read.read()` 还为此多读
       一次层号（`read_floor`，又一次模型往返）。三处全部删掉：
       - `overlay.py::_deliver_monsters`：只填 `self._monsters`，**一个字节都不碰
         `_map_history`，也不再 `mapHistoryChanged.emit()`**（地图栏不会闪了）；
       - `read.py::read()` 手册分支：不再 `read_floor()`，`Reading` 也不带 floor；
       - 统计只剩一个入口：那一行右端的 **↻**（`refreshFloorCounts`）。
       回归测试：`test_manual_read_does_not_touch_map`（断言地图那层原样）、
       `test_deliver_monsters_only_fills_the_monster_list`、
       `test_monsters_pipeline_does_not_touch_map`（`read_monster_counts` 一次没被调）。
       - `Ran 349 tests ... OK`、`_synthetic.log` 全部通过、`check_scenarios` 全部干净、
         `smoke_close 6` 退出码 0。

   25. **↻（每层刷新）= 读这张地图，把"这层有哪些怪、各几只"读出来写进去**
       （owner：「刷新会读图并统计有哪些怪吗」→「不要回填」→「开工吧」）：
       - 新读取 `read.read_floor_monsters(image, known=手册怪名)`：一次请求，
         **不再要求先有名单**（以前只能"给定名字填数字"，一层没加过怪就报
         「这层还没加怪」，owner 实测被这句话卡住）。
       - **必须关掉思考**：同一个模型开着思考时实测 58-130 s，还会把 12000 token
         的输出预算全烧在推理上、正文空着；带 `thinking: {"type": "disabled"}`
         之后 **1.2-1.4 s** 就有结果（`tools/scan_once.py` 实测）。
       - 代价：数量会飘（同一张图 4 次实测 红色史莱姆 4/5/6/6、初级法师 6/6/6/1），
         所以数量在界面上可改。owner 明确**禁止"连问 3 次取中位数"**这种方案。
       - 落库 `_apply_scan`：按名字合并 —— 已有的保序、保「拿过了」、保图标，只更新
         数量；图上新出现的追加；**图上没读到的不删**（不静默删用户的手动记录）。
       - 任务行：「读 4层 的地图…」→「4层：读到 6 种怪（新增 3）」/「统计失败：没认出怪」；
         统计中那行的 ↻ 变「…」。没截图时仍提示「先点「读地图」」。
       - 测试：`Ran 352 tests ... OK`；`_synthetic.log` 56 项全部通过；
         `check_scenarios` 全部干净；`smoke_close 6` 退出码 0。

## 2. 已经完成的重设计部分


| 改动 | 在哪 | 证据 |
|---|---|---|
| 工具栏去掉噪音文字（"只刷新人物信息，不读地图"） | `OVERLAY_QML` 刷新按钮旁 | `docs/capture/_chips2.png` |
| 技能区改横向胶囊（`先攻 ×3`），卡片高度按胶囊行数自适应 | 技能区 `Flow` | `docs/capture/_chips.png`、`_chips2.png` |
| 「＋」加怪改成模板下拉：第一行空白模板，后接 132 个怪物模板（来自 `Downloads/xinxin`、`xinxin2new` 两座塔的 `project/enemys.js`），**每行带 18px 缩略图** | `addTplPopup` + `monsterTemplates()` + `Controller.addMonsterTpl` + `_load_monster_templates()` | `docs/capture/_tpl_list.png`（旧）、`_tpl_icons.png`（带缩略图）；`Controller.monsterTemplates` 实测 132 条，其中 127 条有图 |
| **模板缩略图生成**：从两座塔的 `project/materials/enemys.png` / `enemy48.png` 按 `icons.js` 的行号切格子、去透明边，落到 `assets/monster_icons/`（127 张，只裁不放大）；`assets/monster_templates.json` 每项加 `icon` / `icon_from` | `tools/build_monster_icons.py` + `_load_monster_templates()`（相对路径 → file:// URL）+ 下拉 delegate | `docs/capture/_tpl_icons.png`、`_tpl_icons_built.png`（127 张拼在一起）；`tests/test_editor.py::MonsterTemplateTest` |
| `任务队列` → `读取记录`，空态文案同步 | 该栏目 | 测试 |
| 读取按钮（读取/读怪物/读地图）按下变深、点完闪绿并显示「读取中」 | 三处按钮 | 真点击历史证据 `docs/capture/_click_test.log` |
| **地图区改成扁平列表**：一行一层 `[缩略图] ▸ ● 地下30   4 怪 · 4 资源`（**每层都带那张截图的小图**，没有图就不占位），卡片里不再套两个可滚动列表 | 地图 `ListView` delegate（`rowThumb` + `rowItem.thumbUrl`，行高 28） | `docs/capture/_map_flat_final.png`、`_mapthumb_map.png` |
| **「这一层」居中弹窗**：地图截图（只缩不放，点开看大图）+ 本层怪/资源 + 「关闭」；Esc 关弹窗不退出程序 | `floorDialog` + `win.floorEntry/openFloorDialog/closeFloorDialog` | `docs/capture/_floor_new.png`、`_floor_empty.png` |
| **「这一层」改成行内编辑**（第三轮返工）：点行 → 这一行就地展开输入框（名字/数量，资源还带效果和图标），保存/删除/取消都在行里，**「保存」是绿底加粗、比旁边两个宽**（不然静态看着三个一样，认不出哪个是确认）；**取消或关弹窗什么都不写**（以前是先把"新怪物"落库、取消后垃圾还在） | `FloorMonEditor` / `FloorItemEditor` + `win.startFloorMonEdit/startFloorMonDraft/stopFloorEdit` | `docs/capture/_floor_new.png`、`_floor_add_mon.png`、`_floor_add_item.png`；`_synthetic.log` |
| **「＋ 加怪」选了就加**（用户两次反馈后定稿）：只列**手册里读到的怪**，没有「手动输入」、没有草稿行、没有二次保存；点一项直接进本层（数量留空，点行再填）；同名已在列表只弹一句提示；手册还是空的就提示「先点「读怪物」把手册读进来」 | `floorMonPopup` + `win.floorMonsterChoices()` / `addFloorMonByName()` | `docs/capture/_floor_add_mon.png`；`_synthetic.log` |
| **编辑怪物参数弹窗重做**：参数带标签（生命/攻击/防御/经验两列），名字在标题行、带当前头像，技能单独一行，头像换成 24px 图标网格（同一只怪的 `_0/_1` 两帧只列一次） | `monEditDialog` + `LabeledField` | `docs/capture/_mon_editor.png` |
| **怪物区**：行 = 22px 缩略图 + 名字 + **一行**摘要（超长省略）+ 右侧 `×N` 数量胶囊；整行 hover + 手型；点行开编辑弹窗（改成 `MouseArea`，合成点击也能测了） | 怪物 `ListView` delegate | `docs/capture/_rows_monsters.png` |
| **状态区**：属性/四色钥匙/破炸飞/金币全部改成「图标 + 数字」小胶囊（`StatChip`），四色钥匙一行、破炸飞+金币一行；刷新收成右上角 `↻` 小图标；**没数据时整块不出现**，只留一句「点「读取」拿生命 / 攻防 / 钥匙」——破折号 `—` 全部消失 | `StatChip` + `win.statusHasData()` + 状态区三块 | `docs/capture/_status_stats.png`、`_status_empty.png` |
| **读取记录**：一行一条 = 缩略图（点开看大图，第三轮加回来的）+ 状态图标（`✓`完成 / `✕`失败 / `…`进行中）+ 说明 + 右侧小按钮（失败「重试」、进行中「取消」） | `tasksHeight()` + 记录 `Repeater` | `docs/capture/_rows_tasks.png` |
| **窗口拉宽/拉矮时的排版**：弹窗宽度上限 432（窗口拉到 900 也不整屏铺开，居中）；「这一层」的地图截图最高 150、但窗口矮时按 28% 收（300 高的窗口里列表仍然看得见）；`preview_overlay.py` 加了第 4 个参数（宽度），可以截任意尺寸 | `floorCard`/`monEditDialog` 宽度、`floorShot.maxHeight` | `_qa_wide.png`（900×700）、`_qa_tiny.png`（300×300） |
| **上次记录只提示、不自动恢复**：关窗口时把手动记录（层 + 怪物参数，**不含血量/钥匙**）存到 `logs/last_session.json`；下次启动顶部出现「上次的记录还在：02:31 · 2 层 / 3 只怪  恢复 / 忽略」。点「恢复」才加载，点「忽略」删文件；图片临时文件已经不在了就清掉 url | `_save_session/_load_session/_session_hint` + `Controller.restoreSession/discardSession/sessionHint` | `_session_banner.png`；`SessionStoreTest`（7 项）；`_synthetic.log`（上次记录有提示 / 点恢复 / 恢复了层与怪物记录） |
| **顶栏闪一下**：读取任务从 running 变成完成 → 顶栏绿一下；变成失败 → 红一下（1.8 秒后消失）。折叠状态下也看得见"读完了 / 失败了"，不用盯着记录区 | `win.refreshFlash()`（按任务状态变化，每个任务只闪一次）+ `barFlash` + `BarFlashTimer` | `_flash_ok.png`、`_flash_err.png`；`_synthetic.log`（读完顶栏闪绿 / 闪一下自动消失 / 失败顶栏闪红） |
| **弹窗里的长列表也有滚动条**：主界面「＋」的模板列表、本层加怪/加资源的下拉，右缘加了细滚动条（和主面板一致） | `tplList`/`floorMonList`/`floorItemList` + `ScrollBar.vertical: ThinBar` | 代码 |
| **手动名字的本层怪借模板缩略图**：手册里没有这只（比如手动打的名字），如果模板库里有同名，就用模板的图 —— 本层列表不再出现"有名字没图" | `win.monsterIconNamed()` 兜底 `controller.monsterTemplates` | `_floor_new.png`（上级魔法师那行）；`_synthetic.log`（本层怪借模板的缩略图 before=0 after=1） |
| **上传图只缩不放**：长边超过 64 缩到 64（`cv2.INTER_AREA`），避免把整张截图原样塞进 assets；不是图片直接拒收 | `_import_icon()` | `test_uploaded_icon_is_shrunk`、`test_import_icon_rejects_non_image` |
| **空白模板加完直接进编辑**：选「（空白模板）」→ 加一只「新怪物」→ 自动打开编辑弹窗（填名字/技能/上传图片）；具名模板不弹（数值已经有了）。自动打开是在 `monstersChanged` 里做的，不在 delegate 里 | `win.monAddTarget` + `Connections.onMonstersChanged` | `_mon_editor.png`；`_synthetic.log`（空白模板直接进编辑） |
| **选模板加怪带缩略图**：`addMonsterTpl` 多收一个 `icon`，选完模板怪物行就有图（第四轮用户反馈"选完没图"） | `addMonsterTpl` + 主界面「＋」下拉传 `modelData.icon` | `_tpl_icons.png`；`test_template_icon_is_kept` |
| **「＋」模板下拉能搜名字**：顶上一条搜索框，边打边过滤（124 只逐个翻太慢）；**模糊匹配**——连续包含优先，其次"字的先后顺序"（搜"史姆"能命中"史莱姆"），**命中的字黄色加粗高亮**；大小写不敏感、**别名也搜得到**（搜"上级"能找到 `炎术士`）；搜索时不给「（空白模板）」、搜不到给一句「没找到这只怪，换个词试试」；回车 = 加第一只匹配的，Esc 先清空再关 | `win.tplQuery` + `monsterTemplatesFiltered()/tplMatches()/addTemplateFromPopup()` | `_tpl_search.png`；`_synthetic.log`（搜索后只剩匹配的行 / 搜别名 / 搜不到有提示） |
| **模板再清一遍：只留"能打的怪"**（用户：「怪物模板里还有不正常的，再清理一遍」）：建库时筛掉三类——① **数值全空**（hp/atk 都是 0 的占位：骷髅王、天使、元素生物、铁守卫…20 条）；② **没有立绘**（源数据 5 个彩色史莱姆 E300~E307 没有 `icons.js` 行号，列表里是空图，认不出是哪只）；③ **数值异常**（hp ≥ 5 万的无敌/剧情怪：剑圣 999999、仙子 9999999、尖角怪 99999、黑暗妖精 100000；def ≥ 9000 砍不动的：黄金/白银史莱姆王的 def 9999；hp ≤ 1 且 atk 0 的空壳：黄金/白银史莱姆；atk ≤ 1 又没金币经验的：邪恶蝙蝠）—— 共 34 条没进库，最终 **89 条** | `tools/build_monster_db.py`（`looks_placeholder()` + `ANOMALY` 阈值） | `_tpl_contact_sheet.png`（89 张图一目了然）；`test_placeholder_stats_are_filtered`、`test_every_template_has_a_picture` |
| **头像只显示一次**（用户：「头像有必要额外再显示一次吗」）：怪物参数弹窗里头像只在标题行出现，**点头像本身就是换图**（没图时显示「＋」），「换图 / 上传图片…」两个小链接挪到名字下面；原来下面那行「头像 + 图 + 换图 + 上传」整块删掉，弹窗也跟着矮了一截 | `monEditDialog` 标题行 + `monAvatarBox` | `_mon_editor.png`；`_synthetic.log`（弹窗里头像只显示一次 = 1 次） |
| **【已定位并修复】测试进程退出时 0xC0000005（那次弹窗的真凶）**：复现出栈了 —— `os._exit()` 被从 Qt 定时器回调里调用（`verify_banner` → `finish` → `os._exit`），`ExitProcess` 执行时 Qt 的渲染/GPU 线程还在跑，原生层就崩了，Windows 弹"Python.exe - 应用程序错误：该内存不能为 read"。**A/B 实测**：旧写法 6 轮崩 1 轮（退出码 3221225477 = 0xC0000005，faulthandler 栈直指 `os._exit`）；改成"正常收尾"（先按顺序拆：停定时器 → 关窗口 → 销毁 QML → 断 controller，再 `app.quit()` 让 exec() 返回、main() 正常返回码）后 **16 轮全过、零崩溃** | `tools/test_ui_synthetic.py` 的 `_graceful_exit()`（`test_ui_clicks.py` 同样去掉 `os._exit`）；复现工具 `tools/repro_synthetic_crash.py N` | `logs/_test_crash.log`（旧写法崩溃时 558 字节栈 / 新写法 0 字节）；**新写法累计连跑 36 轮零崩溃**（10 + 6 + 20）；`tests/test_editor.py::NoHardExitTest` 扫全仓库 AST，禁止再出现 `os._exit(`；`tools/preview_overlay.py` 收尾也改成 `_teardown()` 后再返回；16 轮 `退出码=0 结果：全部通过`；`unittest` 290 全过；`smoke_close.py` 退出码 0 |
| **测试进程不再打扰桌面**（用户：崩溃弹窗是测试进程弹的）：`tools/test_ui_synthetic.py` 和 `tools/preview_overlay.py` 启动时 ① `SetErrorMode(0x1|0x2|0x8000)` —— Windows 不再为它们弹"Python.exe - 应用程序错误"的模态框；② `faulthandler` 写 `logs/_test_crash.log`，真崩了看栈；③ 窗口挪到屏幕外 `x=y=-6000`（`grabWindow()` 照样渲染，实测截图不变） | 两个工具里的 `_quiet_crash_dialogs()` + `window.setProperty("x", -6000)` | `_synthetic.log` 仍然 177 项全过；`_offscreen_probe.png` 证明屏幕外渲染正常 |
| **崩溃加固（用户遇到 "Python.exe 应用程序错误：该内存不能为 read"）**：① 启动时开 `faulthandler` 写 `logs/crash.log`（原生访问违例也能留下各线程的 Python 栈）；② 收尾按顺序来：先停定时器/置 `_closing`、**先销毁 QML 树再断开 controller**（`sendPostedEvents(DeferredDelete)` 才会当场销毁，`processEvents` 不会），收尾噪音从 65 行降到 1 行；③ 后台线程统一走 `_start_thread()` 登记，退出时最多等 2 秒收工，关闭后 `_post()` 直接丢弃回调，不再往可能已销毁的对象上发信号；④ 留逃生口 `CHAITA_RENDER=software`（软件渲染，绕开显卡驱动）；⑤ 一键起停自检 `tools/smoke_close.py`（发 WM_CLOSE 走正常退出，报退出码 + crash.log 大小） | `_enable_crash_log()` / `_render_backend_hint()` / `_teardown()` / `_begin_shutdown()` | `tools/smoke_close.py` 实测：普通渲染 + 软件渲染各 3 次，退出码 0、`crash.log` 0 字节、stderr 只剩 1 行启动记录 |
| **修：地图里加怪后技能区不同步**（用户：加怪后技能没更新）：`skillStats` 原来只挂 `monstersChanged` 一个通知，而加怪走的是 `mapHistoryChanged` —— 数据变了但界面不刷新。现在加一个 `skillStatsChanged` 信号，`monstersChanged` 和 `mapHistoryChanged` 都接上它 | `Controller.skillStatsChanged` + `Property(notify=...)` | `_synthetic.log`（加怪后技能统计立刻算上这只怪 / 技能区界面也跟着刷新）；`test_skill_stats_only_map_monsters` |
| **「这一层」的本层怪也改成一行直接改 + 资源去重 / 效果自动带出**（用户四连问：点怪物就改所有、缩略图不放大、加资源有重复、效果还让我填）：① 本层怪每行就是 `缩略图 | 名字框 | ×数量框 | ×删除`，**点数量只改数量**（`saveFloorMonsterField(floor, index, "count", text)`），不再弹整行编辑；② 缩略图单独一个 `objectName: floorMonThumb` 的点击区（z 抬高），点开按整数倍放大看大图；③ `itemChoices()` 改成**按图标去重**（红药水/红血瓶同图只留一条，8 种而不是 10 条）；④ 效果不再让用户填：`tools/build_item_effects.py` 从两座塔的 `project/items.js` + `data.js` 解析 `itemEffectTip` 并代入 `core.values.*`，生成 `assets/item_effects.json`，加资源时自动带出（红血瓶=体力 +150、红宝石=攻击力 +2…），下拉里也标出来 | `saveFloorMonsterField` + 本层怪行 QML + `game/iteminfo.py` + `assets/item_effects.json` | `_floor_items.png`、`_floor_add_item.png`；`test_item_choices_are_deduped_by_icon`、`test_item_effects_come_from_game_data`、`test_adding_item_fills_effect_automatically`；`_synthetic.log`（本层怪是可直接编辑的行 / 每只怪一个数量框 / 点数量改完就写进数据 / 点缩略图能看大图 / 加资源列表没有重复图标 / 加资源列表带效果） |
| **「这一层」加资源：整条工作流重写**（用户：「地图上添加资源的工作流完全不对，重写 UI 和交互逻辑」）：资源行变成**直接在列表里改**——`图标 | 名字 | 效果 | ×数量 | ×删除` 全是输入框/按钮，改哪个字段就存哪个字段（`saveItemField(floor, index, field, text)`，失焦/回车写库），不用再「点行 → 展开编辑 → 填 → 保存」四步；**加完资源光标自动落到那一行的数量上**（选资源 → 直接打数量 → 回车，两步）；点图标展开一行图标换图（同时记进`assets/items/map.json`，下次同名资源自动带图）；行尾 × 直接删；名字清空 = 删掉这条。顺手删掉不再用的 `FloorItemEditor` 组件 | `saveItemField` / `setFloorItemIcon` / `removeItem` + 资源行 QML | `_floor_items.png`、`_floor_add_item.png`；`FloorItemFieldTest`（4 项）；`_synthetic.log`（加完就是可编辑的行 / 加资源后光标在数量框 / 行里改数量/效果直接落库 / 点 × 删掉） |
| **缩略图能放大 + 技能只看地图上的怪**（用户：「缩略图要能放大」「技能只显示地图上添加的怪的技能」）：看大图改成**整数倍放大**（小图标 19×16 也按 ×2/×3… 放大，`smooth: false` 最近邻，像素画是清晰方块、不糊），大图仍然只缩不放，底部写「×N · 点任意处关闭」；「这一层」里怪/资源的 14px 小图标也能点开看大图；技能区只统计**地图记录里出现过的怪**（手册里读了但没加到地图上的怪，技能不往这儿堆），技能明细同样按这个过滤，空态文案改成「地图上加过怪才有技能」 | `previewShot` 的 `zoom` + `Controller.mapMonsterNames` + `_get_skill_stats` 过滤 | `_zoom_preview.png`、`_map_flat_final.png`；`test_skill_stats_only_map_monsters`；`_synthetic.log`（小缩略图被放大 / 放大是整数倍 / 提示写着倍数 / 地图上没加的怪的技能不显示） |
| **技能：一行一个 + 每行可填数值**（用户：「技能的显示方式完全不对要一行一个，要能改计算用的数值」，「同名技能在第一层和第 50 层的数值是不一样的」）：怪物参数弹窗里技能是**一行一个**「名字 | 数值框 | ×」，数值框按回车/失焦写回；下面「＋ 添加技能」展开目录（库里 78 个已知技能，带搜索、点一下加一行、再点去掉，行变绿写「已加」），底部「完成（已加 N 个）」收列表；面板技能区也改成一列 「技能名　数值 30%　×几只怪带」。**数值挂在怪物身上**（`monster["skill_items"] = [{name, value}]`），不是技能目录上 —— 同名技能不同层可以填不同的值；`skills` 字段仍保留成"名字空格串"给老代码/统计用 | `build_monster_db.py`（`skill` / `enemy_skill` 表 + `enemy.skills` 列） + `Controller.skillCatalog` + `skillItems/setSkillValue/removeSkill/toggleMonSkill/pickSkill` | `_monedit_skill.png`、`_map_flat_final.png`；`SkillValueTest`（4 项：JSON 往返、同名不同值、老数据兼容、坏 JSON 不瞎猜）+ `SkillCatalogTest`（4 项）；`_synthetic.log`（一行一个 / 每行一个数值框 / 点行加减 / 填 30 / 保存后带着值） |
| **怪物模板改成数据库 + 同类型分组 + 编号**：从两座塔的 `project/enemys.js` 重抽全部数值，**同类型的排在一起、类型之间按游戏里的出场顺序**（史莱姆 → 蝙蝠 → 骷髅 → 丧尸 → 石头 → 法师 → 守卫 → 剑士系 → 骑士 → 魔王 → 龙 → …；家族**先按名字里的物种词认**（史莱姆/蝙蝠/骷髅/丧尸/龙/剑士/法师/守卫/骑士/魔王…），认不到才用 key 去掉颜色/大小/阶位修饰词；家族名次 = 家族里最早出现的那个怪在源文件里的位置，家族内部按作者顺序），名次就是编号 `#001..#089`；**同一张图只留一行**（按**画面**去重：原尺寸逐像素比一次，尺寸不同就缩到 32×32 再比，只看"18px 缩略图看着一样"这个程度；颜色变体——绿史莱姆/白银史莱姆、史莱姆人/水银人——差得远，保留）；原始模板最后剩 89 条，15 个重复名字并进 aliases，别的叫法记进 `aliases`（`上级魔法师` 并进 `炎术士`，本层手动打的旧名字照样借到图）；源数据里自己标了「已弃用」的、占位怪「新敌人」直接不进库 | `tools/build_monster_db.py` → `assets/monster_templates.db`（SQLite，表 `enemy`）+ `_load_templates_from_db()`（没库退回旧 JSON） + 下拉的 `#编号` 文本 | `_tpl_numbered.png`；`test_templates_grouped_by_family`、`test_templates_have_family_column`、`test_id_reuse_does_not_break_family`（剑神不能被排进史莱姆）、`test_templates_do_not_repeat_a_picture`、`test_no_two_templates_look_the_same`（两两缩到 32×32 比，均值必须 > 6.5）、`test_template_db_is_used_when_present`；`_synthetic.log`（下拉里有编号） |
| **「这一层」加怪**：下拉只列手册里读到的怪（带缩略图、**没有手动输入**），**选了直接加进这一层**（数量留空，点那一行再填）；已有的怪不重复加、只给一句提示；本层怪行按名字显示缩略图 | `win.floorMonsterChoices()` / `addFloorMonByName()` / `win.monsterIconNamed()` | `_floor_add_mon.png`、`_floor_new.png` |
| **「这一层」加资源**：下拉只列素材库里的已知资源（红血瓶/蓝宝石…带图标，**没有手动输入**），**选了直接加**（数量留空，点行再填）；图标按名字落定 | `Controller.itemChoices()` + `floorItemPopup` + `addFloorItemByName()` | `_floor_add_item.png`；`test_item_choices_are_known_resources` |
| **「这一层」的下拉不耷拉出弹窗**：高度按条数算（`contentHeight` 在 delegate 没建完时偏小，会把最后一行裁掉，实测只露一条边）；按钮下面放不下就自动翻到按钮上方，下拉始终留在卡片里 | `floorTplPopup` / `floorItemPopup` 的 `height` + `y` 绑定 | `_floor_add_mon.png`、`_floor_add_item.png`（往上翻） |
| **编辑怪物：技能有候选**：手册/模板里出现过的技能做成胶囊，点一下加进「技能」框、再点移出 | `win.skillCandidates()/monSkillInUse()/toggleMonSkill()` | `_mon_editor.png` |
| **编辑怪物：头像不再挡路 + 支持上传**：默认只显示一行（头像预览 + 换图 + 上传图片…），点「换图」才展开图库；上传的图保存时复制进 `assets/monster_icons/` | `monEditIconUrl()` + `monIconPickerOpen` + `FileDialog` + `saveMonsterFull()` | `_mon_editor.png`；`test_save_monster_with_uploaded_icon` |
| **底部纠错区默认收起**：只占 26px 一行「✎ 发现读错了？点这里直接说」，点开才展开输入框（58px）+「收起」；有回复时收起态直接把回复显示在这一行。数据区因此多出 32px | `win.chatExpanded` + chatBar 高度 | `_chat_collapsed.png`、`_chat_expanded.png` |
| **首次使用引导**：面板全空时最上面一行「把游戏窗口切到前台，点「读取」：它会自己判断读的是人物、地图还是怪物手册」，读到数据后自动消失（状态区的空态提示也只在"只缺状态"时出现，不重复） | `win.isEmpty()` + contentColumn 顶部 Text | `_first_run.png` |
| **删除这一层**：「这一层」弹窗左下加"删除这一层"，**两步确认**（点一下变红"确认删除？"，3 秒不点或换层自动复原），删完整层记录消失、弹窗自动关 | `Controller.removeFloor` + `win.floorDeleteArm` + `floorDisarmTimer` | `_floor_delete.png`；`tests/test_overlay.py::test_remove_floor` |
| **细滚动条**：主内容 / 技能 / 读取记录 / 「这一层」正文，内容超出时右缘出现 4px 竖条（滚动才加粗），不再让人以为"就这些" | `ThinBar` 组件 + `ScrollBar.vertical` | `_scrollbars.png` |
| **取消的记录不再显示成 ✓**：取消态用灰色 `⊘`、文字转灰，和"读成功"区分开（之前取消的看起来像成功，实测截图发现） | 记录行 `cancelled` 分支 | `_rows_tasks.png` |
| **读取记录空态说明「读取」会自己判断画面**：文字改成"点「读取」自动判断画面（人物 / 地图 / 手册），每次读取都记在这里" | 记录空态 | 代码 |
| **技能胶囊可点**：点「先攻 ×3」在下面列出"带这个技能的是哪几只怪"（点第二下收起；怪物清空/重读后自动收起），打法决策不用再翻手册 | `win.skillFocus` + `win.skillMons()` | `_skill_focus.png` |
| **状态区显示读取时间**：属性行右上是「02:07 读取」，数据放了多久一眼就知道该不该重读 | `_apply_status` 记 `statusAt` + QML 文本 | `_ui_after.png` |
| **折叠态摘要**：收起时也看得到 生命 + 四色钥匙（没数据时提示"展开后点「读取」"），折叠高度 44→56；标题旁加 ▸/▾ 提示可以点 | `bar` + `StatChip` | `_collapsed.png`、`_collapsed_empty.png` |
| **当前层标记**：地图列表里"现在这层"（塔名最后一段）用金色 ● 标出来，不用一层层找 | 地图 `ListView` delegate | `_ui_after.png` |
| **读取记录显示已用秒数**：进行中的那条写成「读取中…（12s）」，一秒一刷，长读取时心里有底 | `_start_task` 记 `started` + `taskClock` | `_rows_tasks.png` |
| **记住窗口位置/大小**：拖动/缩放后 600ms 写 `logs/ui_state.json`，下次启动照原样摆回去（夹在屏幕内，至少留 60×40）；折叠时只记位置不记尺寸 | `Controller.rememberWindow/_flush_ui_state` + `_apply_ui_state/_geometry_from_state` + QML `rememberGeometry` | `tests/test_overlay.py::WindowStateTest`；实测写入 100,150,360×640 重启后仍是 100,150,360×640 |
| **本层待办：勾掉打过/拿过的**（用户："记录更准、更好查"）：本层怪的每行行首一个 `○`，点一下变绿 `✓`（再点撤销），资源行同理；弹窗标题、面板里的地图行都跟出「· 剩 N」，全勾完显示绿色的「· 清了」。只改一个布尔值、不重排，所以勾完手指还在原位；`done` 跟 `icon` 一起在每次整行重建时带过去（改数量 / 重读数量 / 重读资源 / 退出重进都不丢） | `Controller._toggle_done/toggleFloorMonsterDone/toggleFloorItemDone` + `_carry_row()` + QML `floorMonDone/floorItemDone/mapRowLeft/floorHeadLeft` | `docs/capture/_done_floor.png`、`_done_map.png`；`tests/test_editor.py::FloorDoneTest`（8 项）、`test_ui_synthetic.py`（12 项真点击） |
| **技能区点开 = 具体效果 + 就地改数值**（用户："点了之后不要展示无效信息，要展示具体效果，效果界面要能改数值"）：点一个技能行，下面是**游戏手册上那句原话**（"怪物首先攻击"/"怪物每回合攻击2次"…），再下面每只带这个技能的怪一行 `名字 ×数量  [值]`，填完回车/点别处就写回**这只怪**（同名技能不同层不同值）。点第二下收起；`Layout.preferredHeight` 在展开时给到 260，不用在小框里挤着滚 | `Controller._get_skill_stats`（每项多 `effect`/`mons`）+ `setMonsterSkillValue` + `chaita/game/skillinfo.py` + QML `skillDetail` | `docs/capture/_skill_effect.png`；`tests/test_editor.py::SkillEffectTest`(6) / `SkillDetailRowsTest`(7)；`test_ui_synthetic.py`（效果文字 / 每怪一个数值框 / 改了写回） |
| **技能说明的数据来源**：`tools/build_skill_effects.py` 解析塔引擎 `project/functions.js` 里 `enemys.getSpecials()` —— 那就是游戏在怪物手册上显示技能说明用的表；动态数字（"附加防御的 X%"）用 … 保留位置，不替用户算。产物 `assets/skill_effects.json`（73 条特殊属性 / 库里 78 个技能全有说明），入口 `chaita/game/skillinfo.py` | `tools/build_skill_effects.py` → `assets/skill_effects.json` | 跑一遍的打印：`特殊属性 73 条` / `库里的技能 78 个，有说明的 78 个`；`SkillEffectTest::test_every_catalog_skill_has_effect` |
| **本层怪名字改成只读**（用户："地图内的怪物显示不需要可以修改名称"）：名字来自手册/模板，是这只怪的身份，能改会和手册记录对不上；要换就从「＋ 加怪」重新挑。数量仍然是行里的输入框，勾选/缩略图/删除都不变 | `floorDialog` 里 `floorMonName`（Text 代替 TextField），提示语改成"点数量改数 · 点 ○ 记打过了（名字只读）" | `docs/capture/_floor_ro.png`；`test_ui_synthetic.py`（"本层怪名字是只读文本" / "没有能改怪名的输入框"） |
| **【已用真实窗口验证并修复】纠错区的三个坑**：① 提示词里带着上一次的 `_raw`（旧原始输出），模型同时看到"改后的 1000→1001"和"旧文本里的 1000"，还会把 `_raw` 当字段抄回来；② 模型偶尔返回空/坏 JSON，旧实现一次就报"没改成功"；③ 空正文时用户看不到任何原因。现在 `correct_status` 只发面板字段（`_public_fields`）、空/坏自动重发（`tries=3`）、失败时给能行动的原因 | `chaita/game/read.py` `_public_fields/correct_status` | `tools/verify_correction_live.py`（真窗口 2 轮指正全对）；`tests/test_read.py` 3 项 |
| **【本轮】按设计系统重做视觉（第一遍）**：新增 `docs/DESIGN.md`（设计理念「一眼看懂，一手能用」+ 参考 + tokens + 组件规范 + 交互原则）。落地：`theme` tokens 对象（3 档表面 / 4 档文字 / brand·ok·danger 语义色 / 4px 栅格 / 等宽数字）、两个复用组件 `CountBadge`/`GhostBtn`；**窗口本身改成 surface1**（原来顶栏单独铺色块，直角会把卡片圆角盖住）；顶栏「读取」变成全界面唯一实心按钮（金底深字），读成功/失败从"整条变色"改成"底边 2px 光条"；四段分区头统一成「▾ 标题 [计数徽标] …… 幽灵按钮」；分区卡片 surface2 + 行 hover surface3（去掉斑马纹）；状态胶囊 22 高 + 等宽数字；底部条加发丝线 | `OVERLAY_QML`（theme / CountBadge / GhostBtn / 顶栏 / 四个分区头 / 怪物·地图·技能行 / StatChip / chatBar） | 截图 `docs/capture/_design_5.png`、`_design_7.png`（主面板）、`_design_empty.png`（空态）、`_design_collapsed.png`（折叠）；`tools/preview_overlay.py` 渲染逐张看过；`unittest 340 项 OK`、`test_ui_synthetic.py 215 项 PASS` |
| **【本轮·3】把对齐"推到一切"**（用户："AI 的交互窗口连对齐都做不到吗"）：底部 AI 纠错区**整个重写** —— 原来高度写死 58 但内容要 ~69（内边距 6+行 22+间距 3+输入 24+底 14），内容直接溢出底边；左右内边距 6 而面板正文是 10。现在：收起 30 / 展开 74 = 内边距(8/12) + 提示行 22 + 间距 6 + 输入行 26，左右内边距 10 与面板正文同一条线；「收起」换成和分区头同一个 `GhostBtn`（右边距与「清空/读地图」完全一致）；「发送」= 这一小块区域的唯一实心按钮。顺手把**四类行的内缩统一**（卡片 4 + 行内 4，内容左 23 / 右 487）、读取记录行/经验行/上次记录条换成 tokens、两个弹窗内边距统一 10px、页脚加显式弹簧（不再靠"不可见 Text 的 fillWidth"把「完成/关闭」顶到右边） | `OVERLAY_QML` chatBar 整块、monsterList/mapList/skillFlick/taskFlick 的 margins、monEditorColumn、floorCard 页脚、sessionHint 行 | 新增 `tools/audit_alignment.py`（像素级对齐体检）+ `tools/time_to_paint.py`（实测首帧内容 ~1.2s，`preview_overlay` 拍照从 1400ms 延到 2200ms，避免拍到"只有顶栏"的空图）；`test_ui_synthetic.py` 新增 6 条几何断言：`聊天输入框左边缘和分区标题同一条线 input=10.0 section=10.0`、`发送按钮右边缘和分区操作同一条线 send=330.0 header=330.0`、`输入框和发送按钮垂直居中对齐`、`聊天区高度装得下内容`、`弹窗标题和卡片左内边距对齐 title=26.0 card=16.0`、`弹窗页脚右边缘和卡片右内边距对齐 footer=314.0 card=324.0`、`编辑弹窗内容左边缘对齐卡片内边距 label=28.0 card=16.0`；`unittest 340 项 OK`、`test_ui_synthetic 224 项 PASS` |
| **【本轮·2】弹窗按同一套 tokens 重排**：「这一层」弹窗（15/600 标题、等宽 `4 怪 · 4 资源 · 剩 5`、怪/资源小节加计数徽标、行内名字 12/500、数量等宽 brand、页脚「完成」= 唯一实心 brand 按钮 / 「删除这一层」= 危险幽灵 / 「关闭」= 幽灵、截图下压发丝线）；怪物参数弹窗（标签 11 + 值 12 等宽、技能行 12/500 + 等宽数值 + `✕`、`保存` 是弹窗里唯一实心按钮）；技能目录（已加态绿→brand 淡底、「完成（已加 N 个）」改描边次按钮，避免一个弹窗两个实心按钮）；读取记录行（状态色 tokens + 11px）；行内 toast 11px 用完成色 | `OVERLAY_QML`：floorCard/floorTop/怪·资源行/页脚、monEditCard/LabeledField/技能行、技能目录、任务行、toast | 截图 `docs/capture/_r2_floor_3.png`、`_r2_menedit3.png`、`_r2_map.png`；`unittest 340 项 OK`、`test_ui_synthetic.py 215 项 PASS` |
| **【本轮】怪物区可以拖拽排序**（用户："为什么我不可以通过拖拽调整怪物显示顺序"）：按住任意一行上下拖 = 调整顺序，拖起来的那行变淡、落点那行顶部一条绿线；松手就落位。顺序**存在列表本身**：改名字、加模板怪（追加到末尾）、再读手册（老怪保持原位、新怪追加）都不再重排 —— 之前三处 `sorted(..., key=name)` 全删了。落点计算没走 QML 的鼠标抓取：实测指针一离开那一行 Qt 就发 `onCanceled`，抓取式拖拽会断在半路；改成和窗口拖动同一套 —— QML 只报"开始/结束"，位置由 Python 每 40ms 读系统光标算（`monDragStart/_tick_mon_drag/monDragFinish`），松开事件丢了也能靠"左键抬起"兜底 | `OVERLAY_QML` 怪物 delegate + `Controller.moveMonster/monDragStart/_tick_mon_drag/monDragFinish` + `_cursor_pos/_cursor_down` | 截图 `docs/capture/_mon_drag.png`（拖拽中：淡行 + 绿线）；`tests/test_editor.py::MonsterOrderTest`(6)、`MonsterDragTest`(5)；`test_ui_synthetic.py` 里"按住拖动会进入排序模式""落点跟着光标走""拖动后顺序按手指落点重排""拖完还是能点行看编辑"4 条（真送 QMouseEvent） |
| **【本轮】「这一层」资源区四条返工**（用户四点）：① **数量的「×」和删除的「×」长得一样** → 数量前面的乘号整条删掉（占位符「数量」+ 琥珀色数字已经说明），删除改成 **`✕`**（更细、hover 变红），怪和资源两行都改了；② **改完不知道存没存** → 每次落库回一个"已存"回执：`savedKey` 记 `item:层:行号` / `mon:层:行号`，那一行在数量框和 ✕ 之间闪一个绿色 **✓**（1.2 秒后自动消失）；③ **资源可以交叉用图 / 效果还让人填** → 资源的**名字、图标、效果全部只读**，跟着道具表走（红宝石=gem_red=攻击力 +2 …），能改的只有数量；换图标入口整块删掉（`floorItemIconRow`/`iconChoices`/`setFloorItemIcon` 一起清掉），同时把 `assets/items/map.json` 里两处错的映射修掉（**黄宝石→gem_green、黄血瓶→gem_purple** 是错的，改成 gem_yellow / potion_yellow —— 这就是"交叉使用图片素材"的根源）；④ **最后没有保存按钮** → 弹窗底部加绿色 **「完成」**：把还在编辑的那一格落库（焦点挪走 → onEditingFinished）、按钮自己闪成「✓ 已保存」、800ms 后关弹窗，底部再写一句「已保存「地下30」」 | `OVERLAY_QML` 资源行/怪物行/页脚 + `Controller.savedKey/_mark_saved/markFloorSaved` + `_get_map_history`（显示层按道具表补图标和效果）+ `addItemFull`/`_attach_items`（落库也以表为准） | 截图 `docs/capture/_item_new.png`（340 宽）、`_item_new_narrow.png`（280 宽）、`_item_saved.png`（✓ 回执）；`tests/test_editor.py::ItemCatalogTest`(6，含"名字和图标对不上一律失败")、`SavedFeedbackTest`(5)；`test_ui_synthetic.py` 新增"资源名字/效果是只读""效果按道具表写死""改完有已存回执""点「完成」→ ✓ 已保存 → 弹窗自己关掉"等 9 条 |
| **清理界面里的垃圾提示**（用户："清理软件内的垃圾提示和信息"）：QML 里"给人看的中文文案"从 **49 条降到 37 条**，剩下的全是按钮/字段名/占位符，没有一句操作说明式的啰嗦话。具体删/改：① 空态不再一区一句（"点「读取」拿生命 / 攻防 / 钥匙""打开怪物手册后点「读怪物」""点「读地图」记录当前这一层""地图上加过怪才有技能…""点「读取」自动判断画面…"全删），**没内容时整块盒子不画**，空面板只剩顶部一句「切到游戏窗口，点「读取」」+ 四个带 (0) 的标题；② 首次引导从 38 字缩成 13 字（不再解释"它会自己判断读的是人物/地图/手册"）；③ 本层的「点数量改数 · 点 ○ 记打过了（名字只读）」「○=拿过了 · 点图标换图」两句删掉（勾选框/图标本身就是入口）；④ 编辑怪物里「数值填这只怪自己的（同名技能不同层可以不一样）」「还没有技能，点下面的「＋ 添加技能」」「没找到这个技能，回车直接加」删/缩成「还没有技能」；⑤ 技能下拉顶部那行「点技能名加一行 · 已加 N 个」删掉，搜索框和「清空」并成一行（省 16px）；⑥ **失败信息不再三处重复**（以前上面红字、读取记录行、底部栏各说一遍，现在底部栏清空），顺手删掉没人看的 `MINIMAL_TEXT = "未接入识别 · 等待画面输入"` 和 QML 里那个空 `statusText` 属性；⑦ 下拉里不再塞"假选项"（手册空时那行「先点「读怪物」把手册读进来」、素材库空时那行「素材库还没配图（assets/items）」看着能点、点了没反应）→ 改成**不弹空下拉**、在弹窗里给一句提示；⑧ 任务行不再写「地下30（读资源…）」「（读其它信息…）」「（资源没读到，点此重试）」这类内部黑话，行首的 …/✕ 加「重试」按钮已经说明一切 | `OVERLAY_QML` 空态/提示/技能下拉 + `win.openFloorMonPicker/openFloorItemPicker` + `Controller._finish/_finish_items_task` | 截图 `docs/capture/_clean_after_empty.png`（空面板）/`_clean_after_map.png`/`_clean_after_floor_empty.png`（0 怪 0 资源）/`_clean_after_menedit.png`/`_clean_skillpick_a.png`/`_clean_after_addmon.png`；`tools/dump_ui_text.py` 数出来的 49→37；`test_ui_synthetic.py` 里"没数据时不再重复一句提示""说明文字不再重复个数""空手册不弹空下拉"等 8 条断言 |
| **【已修】右上角 ✕ / Esc 点了没反应（"我怎么关不掉了"）**：`Controller.quit()` 上的 `@Slot()` 在"加资源工作流重写"那一轮丢了（对比 `logs/overlay_before_itemflow.py` 有、`logs/overlay_before_floorinline.py` 没有），PySide 不注册就**不报错**，QML 只有一句 `TypeError: Property 'quit' of object Controller(...) is not a function`，于是关窗两条路全死。现在补回 `@Slot()`；另外输入框里有焦点时 Esc 原来**什么都不做**，改成先收起纠错区、再按一次才退出 | `Controller.quit`（补 `@Slot()`）+ QML `chatInput.Keys.onEscapePressed` | `tools/check_close.py a`（点 ✕ → **0.01 秒退出**，窗口立刻消失）、`c`（Esc 收起纠错区 → 第二次 Esc 0.01 秒退出）、`b`（弹窗开着时点右上角关的是弹窗）；新增 `tests/test_editor.py::SlotSignatureTest::test_every_qml_call_is_a_slot`（AST 扫 QML 里 `controller.xxx(`，缺 `@Slot` 直接失败） |
| 顺手修掉的坑：① `win.floorItems/addFloor*/editFloor*` 曾被误写进 `floorItems` 函数体里（函数套函数，外面调不到）；② 素材库图标列表原来挂在第一张地图卡片的 `Component.onCompleted` 里，卡片拆掉后就空了 → 挪到窗口的 `Component.onCompleted`（资源行内编辑的图标行要用它） | `win` 顶层函数 / `Component.onCompleted` | 代码 + `_floor_add_item.png`（图标行 8 个图标） |

## 2.5 交互速查（当前实现，给接手的人看）

**启动**
- 窗口回到上次的位置/大小（`logs/ui_state.json`；删掉就回默认右上角）。
- 有上次记录时顶部一条「上次的记录还在：02:31 · 2 层 / 3 只怪　恢复 / 忽略」——**不自动恢复**。
- 什么都没有时顶部一句使用引导「把游戏窗口切到前台，点「读取」：它会自己判断…」。

**读**
- 顶栏「读取」= 自动判断画面（人物 / 地图 / 手册）；分区「读怪物」「读地图」= 明确指定，画面不符会直接说清楚该切到哪个画面。
- 读取中：顶栏显示「读取中…（并行时带数量）」；记录里那条写成「读取中…（12s）」。
- 读完/失败：顶栏闪 1.8 秒（绿 / 红），折叠着也看得见。

**看**
- 状态区：属性 / 四色钥匙 / 破炸飞 / 金币 全是「图标 + 数字」胶囊，右上「02:07 读取」+ ↻（只刷人物）。
- 怪物区：缩略图 + 名字 + 一行摘要 + ×N 数量胶囊，点行开参数编辑；**按住一行上下拖 = 调顺序**（拖起来那行变淡、落点那行顶部一条绿线；顺序存列表本身，读手册/改名/加怪都不会把它重排）。
- 地图区：一行一层 + 「N 怪 · M 资源」+「· 剩 K」（全勾完是绿色的「· 清了」），当前层前面有金色 ●；点行开「这一层」。
- 技能区：一行一个「先攻  数值 30%  ×3」，**点一下展开**：先给这个技能的具体效果（游戏手册上的原话），再列带它的怪，每只一行的「值」框直接改（值挂在怪身上，同名技能不同层不同值）；再点收起。
- 读取记录：缩略图（点开看大图）+ 状态图标（失败 ✕ / 进行中 … / 取消 ⊘，**成功不画**）+ 说明 + 重试/取消；右侧贴 4px 显示读取时间。

**改（都在原地，不叠第二层弹窗）**
- 搜索框（「＋」模板、技能下拉）：边打边过滤，连续包含优先、其次按字的先后顺序（打「史姆」也能出「史莱姆」），命中的字**黄色加粗**；搜不到时给一句提示；输入框高度和上下内边距是一起调的（不然 20px 高会裁掉字的上半截）。
- 地图列表：一行一层，行首是这一层读到时那张截图的缩略图（没有截图就不占位），点这一行打开「这一层」弹窗看大图和本层怪/资源。
- 点怪物/资源的缩略图 = 看大图（小图标按整数倍放大，像素画不糊），点任意处关掉。
- 怪物参数弹窗：标题行是「头像 + 名字」（点头像 = 换图，名字下面有「换图 / 上传图片…」小链接）；生命/攻击/防御/经验各一格；**技能一行一个**：`名字 | 数值 | ×`，数值是**这只怪自己的**（同名技能不同层填不同值），填完回车/点别处生效；「＋ 添加技能」展开目录（78 个已知技能、可搜、点一下加一行、再点去掉，没收录的直接打字「添加「xxx」」），**「完成（已加 N 个）」**收列表，**最后再点「保存」**才落到数据里。面板技能区同样一行一个：`名字  数值 xx  ×N`，**只统计地图上加过的怪**（手册读到但没加到地图的怪不算）。
- 「这一层」的怪：每行 `○ 缩略图 名字 数量 ✕`，**名字只读**（要换名字就删掉重新从「＋ 加怪」挑），点数量就只改数量（前面不再画 ×）；点缩略图看大图；**点行首 ○ = 打过了**（变成实心 ●，再点撤销），标记过的行名字变灰；改完数量那一格底色闪一下（1.2 秒）。怪和资源两段的「数量」「✕」列宽对齐。
- 「这一层」的资源：**只改数量**——`○ 图标 名字 效果 数量 ✓ ✕`，名字/图标也**只读**，效果按道具表**写死**（红宝石=攻击力 +2、蓝宝石=防御力 +2、绿宝石=敏捷 +1、黄宝石=全属性提升…）；点图标能看大图但**不能换图**；「＋ 加资源」选一个，光标自动落到数量上，打数字回车即可；「○」= 拿过了。
- 「这一层」底部：`删除这一层`（两步确认）+ 绿色 **「完成」** + `关闭`。完成 = 把还在编辑的那格落库 → 按钮变「✓ 已保存」→ 关弹窗 → 底部写一句「已保存「地下30」」。
- 待办勾选只是"用户自己的进度"：不改数量、不重排、不进游戏数据；`done` 和换过的图标在每次整行重建时都会跟着带过去（改数量 / 重读数量 / 重读资源 / 退出重进都不丢）。
- 「编辑怪物」（手册参数）：名字 / 生命 / 攻击 / 防御 / 经验（带标签）/ 技能（下面一排候选，点一下加/移出）/ 头像（默认一行，点「换图」展开图库，或「上传图片…」）。
- 删除 = 把名字清空后保存（和以前一致）。

**折叠**
- 收起后：生命 + 四色钥匙摘要、右下 ↻ 快捷刷新、顶栏照样闪光。

**退出**
- ✕ 或 Esc 退出，退出时把手动记录存进 `logs/last_session.json`（**不含血量/钥匙**，下次只提示）。

## 3. 剩余（都要等 owner 决定或环境具备，不是单方面能推进的）

- **全局热键**（例如 Ctrl+Alt+R 直接读一次）：能在游戏抢焦点时用，但会占用系统组合键，**需要用户同意**再做。
- **聊天纠错的能力边界**：已在真实窗口上跑通（`tools/verify_correction_live.py`，改状态面板的字段 100% 照做、没提到的字段不动）。但它**只能改状态面板**，说「这层还有 2 只蓝史莱姆」改不到本层怪/资源 —— 那需要让模型返回"本层增量"（新 schema + 合并规则），得 owner 点头再做。
- **还没做的"更好查"**：跨层按怪名/资源名搜（"蓝宝石在哪几层"）、点怪物跳到它在的层。当前只有"一行一层 + 剩 N"。
- **上传图片的系统文件框**：只能手动点；落盘、缩图、保留旧图都有单测。
- **5 个彩色史莱姆没有缩略图**（橙色/紫色/蓝色/青色/黄色）：xinxin2 的 E30x 号怪在 `icons.js` 里没有行号，下拉里只显示名字；要补得先弄清引擎怎么画它们。
- 下拉里的缩略图是精灵表的**第一帧**（32×32 格子裁出来），不是动画；想要动图得在 QML 里做两帧切换。
- 数据仍然只在内存 + 退出时快照（`logs/last_session.json`，只提示不自动恢复）；**如果希望启动就自动载入上次记录**，需要 owner 确认（会引入"旧数据被当成当前数据"的风险）。

## 4. 统一规范（做的时候照这个来）

- 按钮：高 20、圆角 4、一致 hover/按下反馈、`cursorShape: Qt.PointingHandCursor`
- 可点行：hover 高亮 + 手型
- 弹窗：同一种卡片（标题 / 内容 / 底部按钮行），Esc 取消、Enter 保存
- 空态：**没内容就整块不画**（标题上的 (0) 已经说明一切）；整个面板只在全空时给一句引导，不要每个分区各来一句

## 5. 每步工作流（**必须按这个来，出事两次了**）

```powershell
# 0) 先备份
Copy-Item chaita\ui\overlay.py logs\overlay_before_<名字>.py -Force

# 1) 改 QML（一次只改一块）

# 2) 先查括号（QML 是独立文件了，闭括号错了整窗白屏）
C:\Users\87790\.conda\envs\chaita\python.exe -c "import io;q=io.open(r'chaita/ui/qml/MainWindow.qml',encoding='utf-8').read();print('depth',sum(l.split('//')[0].count('{')-l.split('//')[0].count('}') for l in q.split(chr(10))))"

# 2.5) 换了塔/改了 items.js 后重建"资源效果表"（界面的默认效果来自它）
C:\Users\87790\.conda\envs\chaita\python.exe tools\build_item_effects.py
#     产物 assets/item_effects.json：每个图标一条（名称 + 效果），入口 chaita/game/iteminfo.py

# 2.6) 换了塔/重建模板库后重建"技能说明表"（技能区点开显示的那句效果）
C:\Users\87790\.conda\envs\chaita\python.exe tools\build_skill_effects.py
#     从塔引擎 project/functions.js 的 enemys.getSpecials() 抽（游戏自己给手册用的描述）
#     产物 assets/skill_effects.json，入口 chaita/game/skillinfo.py

# 3) 全量测试（必须全过；只看最后三行）
C:\Users\87790\.conda\envs\chaita\python.exe -m unittest discover -s tests 2>&1 | Select-Object -Last 3

# 4) 不碰鼠标的界面自检（弹窗开/加/改/关 + Esc 都走真 QML；改弹窗必跑）
C:\Users\87790\.conda\envs\chaita\python.exe tools\test_ui_synthetic.py
#    结果看 docs/capture/_synthetic.log，最后一行要是「全部通过」

# 4.2) 所有场景渲染一遍：查 QML 运行期警告 + 空图（截图上完全看不出来的接线错误）
C:\Users\87790\.conda\envs\chaita\python.exe tools\check_scenarios.py
#    每个场景选一个分辨率跑 preview_overlay，抓 stderr 里的
#    "Unable to assign / TypeError / is not defined / Binding loop"，
#    并检查图不是空的；最后一行要是「结果: 全部干净」
#    图落在 logs/_scenarios/<场景>.png，可以逐张看

# 4.5) 真程序起停自检（发 WM_CLOSE = 点 ×，验退出码和有没有崩）
C:\Users\87790\.conda\envs\chaita\python.exe tools\smoke_close.py 8
#     显卡驱动可疑时：tools\smoke_close.py 8 --software（等价 CHAITA_RENDER=software）
#     崩了看 logs/crash.log（faulthandler 写的各线程 Python 栈）

# 4.6) 纠错链路在**真实游戏窗口**上验一遍（会真的花两次 API 调用）#      游戏窗口开着、画面是地图或人物面板时跑；--rounds 2 连发两条指正，
#      检查"改对了、上一轮没被改回去、没提到的字段没动、reply 不是空的"。
#      截图和结果落在 logs/live_correction_<时间>/（window.png + report.json）
C:\Users\87790\.conda\envs\chaita\python.exe tools\verify_correction_live.py --rounds 2

# 4.7) 关窗口这条路（改了关闭按钮 / Esc / 弹窗遮罩就跑一遍；每条都是独立进程）
C:\Users\87790\.conda\envs\chaita\python.exe tools\check_close.py a   # 点右上角 ✕：多久退出、窗口有没有立刻消失
C:\Users\87790\.conda\envs\chaita\python.exe tools\check_close.py c   # 光标在纠错输入框里按 Esc（先收起、再退出）
C:\Users\87790\.conda\envs\chaita\python.exe tools\check_close.py b   # 「这一层」开着时点右上角（关的应该是弹窗）

# 5) 渲染截图，自己看（空白 = 改坏了）
#    第三个参数：map=有数据的地图/怪物/记录（默认），floor=打开「这一层」弹窗，
#                empty=全空（检查空态：状态区只留一句话、没有破折号）
#    floor-add-mon / floor-add-item = 加怪/加资源下拉，monedit = 怪物参数弹窗，
#    floor-edit-item = 资源行内编辑（看绿底「保存」按钮），
#    tpl = 「＋」模板下拉（看编号 #001..#124 和缩略图），
#    tpl-search = 下拉里搜"史莱姆"的过滤状态，
#    monedit-skill = 怪物参数弹窗里的技能下拉（78 个已知技能 + 勾选态），
#    tpl-fuzzy = 打「史姆」的模糊搜索结果（看高亮），
#    tpl-search-long / monedit-skill-long = 输入框里塞一长串（看会不会裁字）
#    collapsed / collapsed-empty = 折叠态（看摘要和提示），skill = 点开技能胶囊，
#    floor-delete = 「这一层」的删除确认态，chat = 底部纠错区展开态，
#    floor-done = 本层勾掉两怪一资源（看行首 ✓ 和标题「· 剩 N」），
#    map-done = 面板地图行（一层「· 清了」、一层「· 剩 N」），
#    flash-ok / flash-err = 顶栏闪光（绿/红），session = 上次记录提示条，
#    search = 地图跨层搜索（输入框 + 命中计数 1/2）
# 第 4 个参数是窗口宽度（默认 340）：preview_overlay.py out.png 300 floor 900
C:\Users\87790\.conda\envs\chaita\python.exe tools\preview_overlay.py docs\capture\_my_check.png 712 empty
C:\Users\87790\.conda\envs\chaita\python.exe tools\preview_overlay.py docs\capture\_my_check2.png 712 monedit

# 6) 不过就回退
Copy-Item logs\overlay_before_<名字>.py chaita\ui\overlay.py -Force
```

**真鼠标点击测试**：`tools/test_ui_clicks.py`（必须显式加 `--allow-mouse`）。
它只在悬浮层能拿到前台时才准；桌面有全屏游戏/别的窗口时会拒绝点击（安全设计，别去掉）。
桌面空闲时跑一次，日志在 `docs/capture/_click_test.log`。第三轮没跑它（桌面一直不空），
「这一层」弹窗、怪物行、状态胶囊、读取记录全靠 `test_ui_synthetic.py` 的合成事件覆盖
（怪物行这一轮从 `TapHandler` 换成了 `MouseArea`，合成点击才测得到）。

## 6. 踩过的坑（照着避开）

| 坑 | 现象 | 正确做法 |
|---|---|---|
| 删 QML 块没数括号 | 整个内容区白屏（截图只剩标题栏） | 删之前数 `{}`，删完查 `depth == 0` |
| `anchors.fill` 直接放在 `Column`/`Row` 子项上 | QML 报 "Cannot specify top, bottom ... anchors on children of Column"，整块不渲染 | 用显式 width/height，或套一层 `Item` 再 fill |
| ListView 的 delegate 用 `findChildren(QObject)` 找不到 | 测试找不到行 | 走 `contentItem().childItems()` 可视树；位置用 `mapToGlobal` |
| 表头整行折叠热区压住按钮 | 点「读怪物」「＋」变成折叠整栏 | 给热区 `z: -1`，沉到按钮下面 |
| `@Slot` 声明参数少于函数参数 | 点「保存」抛 `TypeError: missing 1 required positional argument` | 声明个数必须和函数参数一致（`tests/test_editor.py` 有 AST 测试守着） |
| **漏写 `@Slot()`（不是写错参数，是根本没写）** | 点了**一点反应都没有**，也不报错：QML 只有一句 `TypeError: Property 'quit' of object Controller(...) is not a function`。`quit()` 就是这样丢的，导致右上角 ✕ 和 Esc 全死（用户："我怎么关不掉了"） | `tests/test_editor.py::SlotSignatureTest::test_every_qml_call_is_a_slot` 直接扫 QML 里 `controller.xxx(`，缺装饰器就失败；关窗路径另有 `tools/check_close.py` 真点一遍 |
| QML 调了不存在的函数 | `Property 'xxx' is not a function`，弹窗关不掉、挡住全屏 | 加函数后立刻加载一次验证 |
| `screen.grabWindow()` 同进程第二次是旧帧 | 多个截图 md5 相同 | 用 `window.grabWindow()` |
| PySide 里 `engine.rootObjects()[0]` 没有 `grabWindow`（说是 QWindow） | `AttributeError: 'QWindow' object has no attribute 'grabWindow'` | 从 `PySide6.QtQuick` **import 一下 `QQuickWindow`**，PySide 才把窗口包成 QQuickWindow；见 `tools/preview_overlay.py` 顶部 |
| 透明悬浮层用 `screen.grabWindow(winId)` 抓成桌面 | 截图里是桌面图标，只有标题栏像悬浮层 | 同上，用 `window.grabWindow()` |
| 合成键盘事件测 Esc 永远失败 | Esc 前后状态都一样、也不退出程序 | 窗口没激活时 Qt 不派发键盘事件（`activeFocusItem` 是 None）。测试里先 `window.requestActivate()`，并用 `QTest.keyClick(window, Qt.Key_Escape)`（`app.sendEvent` 不走 Shortcut） |
| 弹窗开着时 Esc 把整个程序退掉 | 焦点不在弹窗上（比如刚关掉叠在上面的编辑框），Esc 落到窗口级 Shortcut | 窗口 Shortcut 里按「怪物编辑弹窗 → 编辑弹窗 → 「这一层」→ 退出」顺序处理；弹窗的 `focus` 用 `visible && !editDialog.visible`，编辑框一关自动拿回焦点 |
| 「这一层」卡片高度少算 10px | 正文最后一行被截掉一半 | 高度里要算上 `floorTop.y`（上边距），否则滚动区比正文矮 |
| 弹窗/列表里改了模型后原地再写 `win.xxx` | `ReferenceError: win is not defined`（delegate 当场被销毁） | 先把 `win` / 层名存进局部变量，再调 `controller.addFloorMonster` 这类会改模型的 Slot |
| 测试收尾时刷一屏 `Cannot read property 'xxx' of null` | 每次窗口销毁都刷几百行，看着像坏了 | 是 QML 在 Python 侧 Controller 已经没了之后重算绑定，只在销毁时出现、不影响运行；运行期没有这类报错 |
| 用脚本整块替换 QML 时把 Repeater 的闭合 `}` 一起换掉了 | `depth 1`，整块不渲染 | 替换区间要停在空态 `Text` 之前，但 Repeater 的 `}` 属于上层；换完必须查 `depth == 0`（第三次踩到） |
| 一排 chip 用 `Flow` 自动换行 | 金币会因数字宽度被挤到第二/三行，数值一变换行位置就变，看着乱 | 语义分组固定成两行（四色钥匙一行、破炸飞+金币一行），别交给 `Flow` 碰运气 |
| 删掉组件后还有旧 id 引用 | `ReferenceError` / 静默不渲染 | `StatIcon` 换成 `StatChip` 后搜一遍旧 id（`taskThumb`、`monIcon` 这类）；替换完 grep 确认没有残留 |
| 真鼠标测试抢前台 | 别人在玩游戏时鼠标被抢 | 用 `--allow-mouse` 显式开启；不玩游戏时再跑 |
| 怪物模板没图，以为 `enemys.js` 里没图就是没图 | 下拉只有名字 | 图在 `project/materials/enemys.png` / `enemy48.png` 精灵表里，`project/icons.js` 的 `enemys` / `enemy48` 段给 id → 行号；32 格子一行一只、两帧（宽 64），48 格子一行一只、四帧（宽 128、每格 32×48） |
| 精灵格直接当缩略图用 | 18px 的框里图案只占中间一小块，看不清 | 先按 alpha 去透明边（`tools/build_monster_icons.py` 的 `trim()`），再交给 QML `PreserveAspectFit`，不做放大 |
| 在 delegate 里调会改模型的 Slot，后面还跟着界面收尾代码 | 数据改了、编辑框不关（组件当场被 Repeater 销毁，后续语句不执行） | 先把编辑态收掉，再调**一个** Slot 把活干完（`addFloorMonsterFull` / `addItemFull` / `saveItemFull`），改完模型后面不要再碰组件状态 |
| 新加的行/编辑块落在列表最后，没滚进可视区 | 用户看不到输入框和"保存/取消"，以为点了没反应 | `win.ensureFloorVisible()`：用短 Timer 等布局算完，再把编辑块滚进视口（加了怪物/资源后也要滚到那一行） |
| 用 `QTest.keyClicks(window, ...)` 打字 | `TypeError: called with wrong argument types` | `keyClicks` 只收 QWidget；窗口版只有 `keyClick(window, key)`，逐字发 |
| 用 `item.isVisible()` 判断"看得见" | 父级隐藏的输入框仍算可见，测试会点到看不见的控件 | 往上走 `parentItem()` 一起判断（`test_ui_synthetic.py` 的 `shown()`） |
| 新增字段被"重建条目"的旧接口抹掉 | 本层怪保存后图没了（`saveFloorMonster` 把条目重建为 `{name,count}`） | 新的 `saveFloorMonsterFull` 先取旧图、调用旧接口、再按名字把图补回去；写完补一条单测守住 |
| 在弹窗 delegate 里"加完顺手再干一件事" | 只加了数据，弹窗没关、编辑没打开（`monstersChanged` 一触发 delegate 就重建，后面的语句不执行） | 先记意图（`win.monAddTarget`）、先关弹窗，再改模型；真正的后续动作放到窗口级的 `Connections` 里做 |
| 在 Qt6 里用 `FileDialog.file` 取文件 | 取不到（Qt6 是 `selectedFile`） | 用 `selectedFile.toString()`；上传图存盘时把 `file:///C:/x` 转成路径（`_import_icon`） |
| QML 传 8 个参数给 Python `@Slot` | 静默不执行 / 报参数不匹配 | 槽声明个数必须和 QML 调用一致（这轮 `addMonsterTpl` 从 6 个加到 7 个，测试里同步改了） |
| 给 Flickable 挂 `ScrollBar` 但它一直亮着 | 内容明明放得下，右缘仍有一条通高竖条（size=1.0 但 visible） | 自己绑 `visible: thinBar.size < 1.0`；另外 `QQuickItem.isVisible()` 只看自己，判断"真看见"要顺父链 |
| 空态文案变两行后框还是 30px | 第二行被裁掉（实测截图） | 空态高度单独给 46px（`tasksHeight()` 里 `n === 0` 分支） |
| 「保存」按钮平时是灰的，只有鼠标移上去才变绿 | 静态一看和「删除」「取消」长得一样，用户问"改完怎么没有确认按钮"（实测截图就是这样） | 主按钮**默认就绿**、加粗、比次按钮宽一点；别把"主色"只放在 hover 态上 |
| 为了"简洁"把每层的截图缩略图从地图行里去掉 | 一层层名字看着差不多，认不出哪层是哪层（用户直接问"为什么把缩略图删了"） | 行首保留 32×22 缩略图（`rowThumb`），没有截图才不占位；**别再为了省地方删它** |
| 模板库直接照搬两座塔的 enemys.js | 里面混着作者留下的空壳（hp/atk 全 0）、无敌剧情怪（hp 9999999）、砍不动的 def 9999、没有立绘的自定义 id —— 加进列表就是"生命 0 攻击 0"这种废条目（用户两次说"还有不正常的"） | 建库时按数值筛：`looks_placeholder()` 判 hp ≥ 5 万 / def ≥ 9000 / hp ≤ 1 且 atk 0 / atk ≤ 1 又无金币经验；没立绘的也不进库（列表是按图认怪的） |
| 用 png 文件 sha1 去重模板图 | 同一条素材在两座塔里被重新编码/换过帧，字节不同但画面一样，下拉里还是两张一样的图（实测 132 条里有 17 条是重复画面，用户喊"有大量重复的模板"） | 按**画面**去重：原尺寸逐像素比（均值 ≤3、差异像素 ≤15%），尺寸不同就缩到 32×32 再比（均值 ≤6.5）；阈值只放到"菜单里那 18px 看着一样"的程度，颜色变体保留 |
| 拿 id 猜怪的家族 | 源数据里塔作者会挪用 id（xinxin2 把 `goldSlime` 给了「剑神·沙士」、`skeletonKing` 给了「魔神·些多」），照 id 分家族会把 BOSS 塞进史莱姆堆里（用户直接问"这个剑神凭什么排在11"） | 家族**先按名字里的物种词认**（史莱姆/蝙蝠/骷髅/丧尸/龙/剑士/法师/守卫/骑士/魔王…），认不到才退回 id；实在没线索的（魔神·些多）写进 `FAMILY_OVERRIDES` 钉死 |
| `E300`、`E336` 这种自定义 id | 去掉数字只剩一个字母，40 只怪全被并成同一个家族「e」 | E 开头的 id 不参与 id 分家族，一律按名字物种词认（紫色史莱姆 → 史莱姆、毒龙 → 龙） |
| 小号 `TextField` 只设 height/leftPadding | 文字上半截被裁掉（实测 20px 高时"史莱姆王…"只剩半截） | 搜索框这类小高度输入框要一起把 `topPadding`/`bottomPadding` 设成 0 |
| QML 里写 `\"` 转义引号 | 整个 QML 是 Python 普通三引号字符串，`\"` 会被 Python 吃掉一个反斜杠，到 QML 变成裸引号把字符串截断（报 `Expected token ':'`） | 富文本用单引号属性（`<font color='#f0d27a'>`），或者把 QML 字符串写成 raw string |
| JS 里 `out += cond` 换行再 `? a : b` | 自动分号插入把语句截断，QML 报语法错 | 整个三元表达式括起来（`out += (cond ? a : b)`） |
| 按名字高亮，但这一行是靠别名命中的 | `fuzzyMatch` 返回 null → 整行渲染成空白 | 没命中就原样显示（`highlightHtml` 返回转义后的原文） |
| 在 Qt 回调里 `os._exit()` 收尾 | `ExitProcess` 时渲染/GPU 线程还在跑，原生访问违例（0xC0000005，Windows 弹"该内存不能为 read"）；偶发、难复现 | 先按顺序 teardown（停定时器 → 关窗口 → `sendPostedEvents(DeferredDelete)` 销毁 QML → 断 controller），再 `app.quit()`，让 `exec()` 返回、用返回码正常退出；复现/回归都跑 `tools/repro_synthetic_crash.py 10` |
| 退出时 QML 还活着、controller 先没了 | 收尾刷一屏 "Cannot read property 'x' of null"，拆到一半还在求值最容易触发底层访问违例 | 按顺序拆：停定时器 → 关窗口 → `deleteLater()` + `sendPostedEvents(DeferredDelete)` 真的销毁 QML → 再断开 controller |
| 用 `processEvents()` 等 `deleteLater()` | `deleteLater` 排的是 DeferredDelete 事件，`processEvents()` 不处理它，对象其实还在（收尾噪音不降） | 显式 `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` |
| 往函数上插代码时插到了 `@Slot(...)` 和下一个函数之间 | 装饰器贴到了新函数上，`test_slot_declares_every_parameter` 立刻报错（声明 1 个实际 2 个） | 插完看一眼装饰器归属，改完就跑全量单测 |
| Property 的 `notify` 只挂一个信号 | 属性依赖两个来源（怪物列表 + 地图记录）时，另一个来源变了界面不刷新（技能区就是这样：地图加怪后技能不变） | 单独开一个 `xxxChanged = Signal()`，把几个来源都 connect 上去，`Property(notify=...)` 用它 |
| 新建 Slot 起了个已有的名字 | 同名方法把老的覆盖掉，老接口的测试全红（我加的 `setItemIcon(floor, index, stem)` 盖掉了`setItemIcon(name, stem)`） | 新接口换个名字（`setFloorItemIcon`），加完先跑全量单测看有没有被同名覆盖 |
| 测试里给新资源名传了图标 | `addItemFull` 会把"名字→图标"写进 `assets/items/map.json`，跑完测试就多出一条假映射（实测多出"宝石"） | 测试里 icon 传空，或者断言前备份/还原 map.json；`itemChoices` 也加了"图标文件不存在就不列出来"的兜底 |
| 放大看图的 Image 同时设 `sourceSize` 和按倍率算的 `width` | 两者互相影响，实测放大后整张图直接不显示了 | 只算 `width/height = 原始尺寸 × 整数倍`，别设 `sourceSize`；`smooth: false` 下 Qt 用最近邻放大，像素画清晰 |
| 技能区直接统计 `controller.monsters` | 手册里读了一堆但地图上没加过的怪，技能全堆在面板上（用户要求只显示地图上的） | 用 `Controller.mapMonsterNames`（地图记录里的怪名）过滤，技能明细 `skillMons` 走同一份名单 |
| 把技能的数值放在技能目录上 | 同一个技能在第 1 层和第 50 层数值不一样，目录级只能留一个值（用户直接指出） | 值挂在**怪物**的技能条目上（`skill_items[index].value`）；面板统计时把各只怪的值都列出来（`values[]`） |
| 技能数值框用 `onTextChanged` 写回 | 每敲一个字就改 `skillItems` → Repeater 重建 delegate → 焦点丢失、打不了字 | 用 `onEditingFinished`（外加 `Keys.onReturnPressed`）批量写回 |
| 技能行和候选列表里出现同名文字 | 合成测试 `click_text` 点到不可点的那一行，看着像"点了没反应" | 点候选要取**最后一个**同名项（`click_text_last`） |
| 同一条信息在两个地方各显示一遍 | 头像在标题行有、下面又单独一行「头像 + 图 + 换图 + 上传」，用户直接问"头像有必要额外再显示一次吗" | 一个信息只留一处：头像放标题行，对着它点就是换图，操作链接放它下面；下面那行整块删掉 |
| 技能列表用浮层下拉盖在弹窗上 | 弹窗只有 200 多像素高，浮层把「保存/删除/取消」整行盖住：用户点不到确认，点下去还落到列表某一行上（用户原话："我怎么给怪加不了技能，我怎么确认？"） | 选择列表**占位展开**（放在 Column 里、卡片跟着长高），按钮永远在下面；再给一个明确的「完成（已选 N 个）」按钮收尾 |
| 下拉面板用 `mapToItem()` 算位置 | 绑定不算依赖、布局一变就不刷新，面板会浮在触发它的输入框上面把点击吃掉（实测：技能下拉怎么点都关不上） | 用普通属性加出来（`monEditorColumn.y + row.y + row.height`）；另外 `Popup` 的"外面按下就关"会和触发控件的 `onClicked` 互相反转，自绘 Rectangle 更省心 |
| 把游戏的 `special` 码当全局表翻译 | 两座塔的码表不一样（xinxin 的 4 = "2连击"，xinxin2 的 4 = "二回攻击"），混着用会把技能翻译错 | 按各自塔的 `project/functions.js` 的 getSpecials 表翻译；技能名里的空格要去掉（整个应用的 skills 是空格分隔的，"BOSS Ⅰ型"会被拆成两个技能） |
| 建库时按"<塔>_<id>.png 存在就拿"猜缩略图 | 两座塔有同名 id（都有 E336），xinxin 的 E336 是毒龙、xinxin2 的 E336 叫"新敌人"，毒龙的图被挂到新敌人头上（实测查库发现） | 以 `monster_templates.json` 里的 `icon_from`（塔:id:尺寸）为准一条条对，别按文件名猜 |
| 按名字去重怪物模板 | 两个塔是同一套美术，`xinxin_darkKnight.png` 和 `xinxin2_darkKnight.png` 像素一模一样，下拉里两只看着是重复 | 按**图片内容 sha1** 去重，一张图一行；没图的（5 只彩色史莱姆）再按名字分 |
| 下拉里加了搜索框，但 `text: win.tplQuery` 两向绑定 | 打字时和写回互相触发，光标乱跳 / 过滤不刷新 | 输入框只做 `onTextChanged: win.tplQuery = text`，外部改属性再靠带相等判断的 `Connections` 同步回输入框 |
| 用 `ListView.contentHeight` 给下拉定高 | 最后一个选项只露一条边（delegate 异步创建，`contentHeight` 当下偏小） | 按条数算：`选项数 * 行高 + 8` |
| 下拉统一往下开 | 「＋ 加资源」在卡片下半截，下拉耷拉出弹窗外，看着像 bug（实测截图） | `y` 绑成"下面放得下就 18、放不下就 `-(height + 6)`"，用 `mapToItem(floorCard, ...)` 判断 |
| 用 `window.setProperty("height", ...)` 做矮窗口截图 | 截图还是 712 高：QML 启动时有一小段"展开"动画，把高度拉回 `savedHeight` | 动画跑完（约 900ms）再设，并同时设 `savedHeight`；`preview_overlay.py` 已经这么处理 |
| 在 Python 字符串里写 QML 正则 `[\s...]` | 导入时报 `SyntaxWarning: invalid escape sequence '\s'` | 源码里写成 `\\s`（两笔），QML 收到的才是 `\s`；改完用 `python -W error::SyntaxWarning -m py_compile` 确认 |
| 启动时"先展开、后恢复尺寸" | 恢复的 360×640 被展开动画拉回 340×712 | 先恢复几何（同时写 `savedWidth/savedHeight`）、再展开；展开动画的目标就是这两个属性 |
| 窗口刚创建就报 x=0,y=0 | 上次记的位置被 0,0 覆盖 | 摆位完成前不记录（`markGeometryReady()` 之后才收） |
| 用 `win.towerLabel` 取塔名 | QML 里是 undefined，标记永远不亮 | 塔名是 Controller 的属性，写 `controller.towerLabel` |
| `json.load` 直接读手改过的状态文件 | 记事本/旧 PowerShell 会写 BOM，读出来报错当成空 | 用 `encoding="utf-8-sig"` |
| 按 className 找 QML TextField | 运行期类名是 `TextField_QMLTYPE_x`，`QQuickTextField` 一个也找不到 | 按 `placeholderText` 属性找（`find_field()`） |

## 7. 其他挂着的事（不属于本目标，但要知道）

- **怪物模板缩略图**：`project/enemys.js` 里确实**没有图片字段**（只有个别 boss 有 `bigImage`），但图在 `project/materials/enemys.png`（32×32 一格、一行一只、两帧）和 `enemy48.png`（32×48、四帧）里，行号由 `project/icons.js` 的 `enemys` / `enemy48` 段给出（id → 行号）。`tools/build_monster_icons.py` 就是按这个切的；剩下 5 个 E30x 彩色史莱姆没有行号，切不出来。
- **境界**：提示词已点名禁止把「剑者/凡阶入门/真仙境九变/领主三阶」写进技能，但**没在真模型上复验过**（本机到模型接口两次超过 3 分钟不返回）。
- **真点击套件**目前跑不了：悬浮层抢不到前台（桌面有其他全屏窗口时），只有不碰鼠标的 `test_ui_synthetic.py` 可用。
  第三轮所有交互（地图行/弹窗/怪物行/记录按钮）都只走合成事件（`_synthetic.log` 62 项），**没在真鼠标下点过**；
  合成事件能覆盖 `MouseArea`，覆盖不了 `TapHandler`（怪物行这一轮已经换成 `MouseArea`）。

## 8. 常用路径

```
chaita/ui/main.py            ← 门面：只把名字摆出来（老调用方按 overlay.<名字> 取）
chaita/ui/qml/MainWindow.qml       ← 界面正文（QML 单独一份，不再是 Python 字符串）
chaita/ui/constants.py              ← 常量、资源路径
chaita/ui/toolkit/              ← 纯函数：desktop / library / pictures / texts / state / api / diagnostics
chaita/ui/controller/           ← 控制器：base（组装）+ reading / monsters / floors / status / chat
chaita/ui/startup.py            ← 崩溃日志、渲染后端、main()、收尾
tests/test_editor.py            ← 编辑逻辑 + @Slot 签名测试
tests/test_integration.py       ← 集成测试（含 MapFloorDialogTest：弹窗自动收起）
tests/test_worker.py            ← 读取链路（桩）
tests/ui_patch.py               ← 打桩范围（按名字铺到 ui 包里所有持有它的模块）
tools/_split_overlay.py         ← 上面那次拆分用的迁移脚本（干跑不加 --write）
tools/check_session_loop.py     ← 会话连问三句的探针（真发请求，见第 10 节）
tools/check_single_instance.py  ← 连开两次只该有 1 个窗口（见第 20 节）
tools/compare_icons.py      ← 出一张「AI 裁的 vs 素材库同款」对比图（见第 22 节）
tools/check_deps.py         ← environment.yml 与代码 import 是否对齐（见第 24 节）
tools/check_test_isolation.py ← 测试 import 阶段有没有污染环境变量（见第 27 节）
tools/_read_end_to_end.py       ← 拿存盘截图跑一次完整「读取」（不碰游戏窗口）
tools/_time_manual.py           ← 量一次「读怪物」耗时（存盘手册页）
tools/_refresh_live.py          ← 验一次「↻」（存盘地图截图，读这层有哪些怪）
tools/check_chat.py             ← 验一次「对话」（真模型一次往返，存盘截图）
tools/dead_code.py              ← 列"定义了但没人用"的函数（只报不改，见第 11 节）
tools/test_ui_synthetic.py      ← 不碰鼠标的界面自检（改界面必跑）
tools/test_ui_clicks.py         ← 真鼠标点击（--allow-mouse）
tools/preview_overlay.py        ← 假数据渲染截图（map / floor / empty 三种场景）
tools/build_monster_icons.py    ← 从两座塔的精灵表切怪物模板缩略图（改模板/换塔后重跑）
tools/coverage_report.py        ← 覆盖率（最近一次 91.6%）
assets/monster_templates.db     ← 怪物模板库（SQLite）：`enemy` 89 条（seq=编号、按图片去重、aliases、skills、family、source_rank）+ `skill` 78 条（技能目录）+ `enemy_skill` 怪物→技能关系 —— 界面读这个
tools/build_monster_db.py       ← 建上面那个库（塔目录换了就重跑）
tools/build_item_effects.py     ← 从两座塔的 items.js 解析资源效果 → assets/item_effects.json
tools/repro_synthetic_crash.py  ← 反复跑界面自检直到崩（复现退出崩溃用）
assets/monster_templates.json   ← 老数据：按名字排，只给 build_monster_icons.py 用
assets/monster_icons/           ← 127 张模板缩略图（build_monster_icons.py 生成，别手改）
logs/overlay_before_mapflat.py  ← 第二轮开工前的整份 overlay.py（回退用）
logs/overlay_before_rows.py     ← 第三轮开工前（怪物区/状态区/读取记录改之前）
logs/monster_templates_before_icons.json ← 加缩略图之前的模板数据（回退用）
logs/crash.log                  ← 闪退现场（faulthandler 写，空文件 = 没崩）
logs/_test_crash.log           ← 界面自检/截图工具崩的话写这儿（同样空 = 没崩）
logs/chaita.log                 ← 运行日志（别删）
logs/last_session.json          ← 上次退出时的层/怪记录（只在界面上提示，不自动恢复）
logs/ui_state.json              ← 上次的窗口位置/大小（删了回到默认右上角）
docs/capture/                   ← 截图证据：`_map_flat_final.png`（地图扁平行）、
                                  `_floor_new.png`（这一层弹窗）、
                                  `_rows_monsters.png`（怪物行）、
                                  `_status_stats.png` / `_status_empty.png`（状态区）、
                                  `_rows_tasks.png`（读取记录）
```

## 9. 界面代码拆目录（2026-10-26）

用户原话：「说了要优雅为什么所有代码写一个文件里？」。拆之前 `chaita/ui/main.py`
是 8384 行一个文件（QML 5226 行塞在 Python 三引号字符串里 + Controller 2300 行 +
一坨工具函数）。拆之后：

| 文件 | 行数 | 里面是什么 |
|---|---|---|
| `chaita/ui/qml/MainWindow.qml` | 5226 | 界面正文，和原来那份**逐字节相同** |
| `chaita/ui/controller/floors.py` | 601 | 地图区 + 「这一层」的行编辑、备忘、刷新 |
| `chaita/ui/controller/reading.py` | 663 | 「读取」这条线：抓图 → 判类型 → 读内容 → 落地 |
| `chaita/ui/controller/base.py` | 520 | 线程/任务队列/窗口尺寸拖动/退出 + 组装 |
| `chaita/ui/controller/monsters.py` | 455 | 怪物区：模板库、加怪、拖动排序、技能数值 |
| `chaita/ui/controller/status.py` | 116 | 状态区文本、选手信息、更新线程 |
| `chaita/ui/controller/chat.py` | 65 | 对话区 |
| `chaita/ui/toolkit/*.py` | 640 | 纯函数：光标/命中测试、模板库、截图落盘、文本、状态文件、API key、错误日志 |
| `chaita/ui/constants.py` | 82 | 常量与资源路径 |
| `chaita/ui/startup.py` | 135 | 崩溃日志、渲染后端、main()、按顺序收尾 |
| `chaita/ui/main.py` | 64 | 门面：把上面所有名字重新摆出来 |

Controller 仍是**一个 QObject**，只是方法分住在几个 mixin 里（PySide6 会把
mixin 上的 `Signal` / `Property` / `@Slot` 都注册进最终类，实测
`metaObject().propertyCount() == 26`、55 个 `@Slot` 一个不少）。
`base.py` 的 `Controller(ChatMixin, FloorsMixin, MonstersMixin, ReadingMixin,
StatusMixin, BaseMixin, QObject)` 只保留 `__init__` 和 14 个信号。

**这次踩到的四个坑（都写进脚本里了，重跑 `tools/_split_overlay.py --write` 可复现）**：

| 坑 | 现象 | 做法 |
|---|---|---|
| 类体里的 `Property(int, _get_active_reads, ...)` 引用的是**方法名** | 方法搬进 mixin 后 `NameError: name '_get_active_reads' is not defined`，整个包 import 不了 | 生成时把 getter 写成 `BaseMixin._get_active_reads`；信号仍留在 `Controller` 类体（Property 的 `notify=` 是同名裸名，顺序不变才找得到） |
| 方法体里的 `from .. import trace` 是按**原来所在目录**写的 | 搬深一层后 `ModuleNotFoundError: No module named 'chaita.ui.game'`，界面属性一读就报 | 搬进 `controller/`、`toolkit/` 的函数体统一多一层点（`from ... import trace`） |
| 测试用 `patch.set(ov, "threading", ...)` 只改了门面 | 拦不住真正干活的那个模块 → 线程真的起来了、桩静默失效（跑一半报 `Signal source has been deleted`） | `tests/ui_patch.py`：按**名字**铺到 ui 包里所有持有它的模块；`QGuiApplication`、`SESSION_PATH`、`_cursor_pos` 同理 |
| `_HTLEFT, _HTRIGHT = 10, 11` 这种一拖多的赋值 | 拆分脚本只认 `ast.Name`，`_HTLEFT` 没被收进 `constants.py` → `NameError`（点窗口边缘缩放就崩） | 生成脚本认 `ast.Tuple` 里的每个名字 |

**验收（这一次实测）**：

```
Ran 345 tests in 57.7s   OK                                    # unittest discover -s tests
==== 结果：全部通过 ====                                        # tools/test_ui_synthetic.py
结果: 全部干净                                                  # tools/check_scenarios.py
退出码: 0  logs/crash.log 大小: 0 字节 = 没闪退                  # tools/smoke_close.py 6
进程→import 287 ms   loadData 798 ms   首帧 941 ms              # tools/startup_regression.py
qml identical: True 235224 235224                              # 和拆之前的 QML 逐字节一致
（345 = 拆分时的 338 + 会话循环 3 条 + collect_icons 2 条 + 抠图守卫 2 条）
```

回退：`logs/backup/overlay_before_split_2026.py` 就是拆之前那份 overlay.py。

## 10. 「读取」的实测：三个真 bug + 两个待决（2026-10-26）

修完三个 bug 之后，拿仓库里存的全尺寸手册页（`docs/capture/_manual_repro.png`，
2582×1390，通天塔1 五只怪）实测：

```
读怪物 21.5 s，5 行，数值和截图逐项对上（80/25/1/1、200/50/10/1、100/30/3/1、
100/26/3/1、120/35/5/1），图标 0 张        ← 修了会话循环 + sprite 卡死之后
读怪物 55.6 s，5 行，图标 5 张              ← 再修掉 collect_icons 的 json bug 之后
一轮（整张 2 MB 图 + 一句话、不用工具）2.1 s
对话 3.0 s，hp 53 → 60，回一句「已将生命从53改为60，其余字段保持不变」   ← tools/check_chat.py
读取全链路 57.1 s，8 只怪 / 7 个资源落地，Event loop 噪音 0 条        ← tools/_read_end_to_end.py
```

### 10.1 一个会话问第二句必崩（**已修**）

「一次读取只开一个会话」改造之后，`agent/core.py` 的 `Session.ask` 每次都用
`asyncio.run()`：每个问题新开一个事件循环、问完就关。框架底下的 httpx 连接池
挂在**第一个**循环上，所以第二句必定：

```
agent_framework.exceptions.ChatClientException:
    service failed to complete the prompt: Event loop is closed
```

真的会打崩「读地图」（一次会话问层号 / 怪 / 资源三句），单测里的假 Agent 走不到
httpx，所以一直没暴露。

- 修法：循环跟着会话走（`Session.__init__` 里 `asyncio.new_event_loop()`，
  每句 `run_until_complete`），加 `close()` / `with` 支持；`core.run`、
  `agent.map.read`、`agent.map.monsters`、`agent.monster.read` 都用 `with`。
- 复现/回归探针：`tools/check_session_loop.py`（连问三句，真发请求）。
  实测：`三句都通过：循环跟着会话走，没有 Event loop is closed`。
- 单测：`tests/test_agent.py::CoreTest::test_session_keeps_one_event_loop`
  （把 `asyncio.run` 换成抛异常，仍要能连问三句）。
- 顺手修掉一个噪音：httpx 的 `AsyncClient.aclose()` 是 GC 时才排到循环上的任务，
  循环先关就变成「Task exception was never retrieved: Event loop is closed」
  （一次读取刷 3 条）。`Session.close()` 现在的顺序是：丢引用 → `gc.collect()`
  → 让循环跑一轮 → 关循环。复测 `tools/_read_end_to_end.py`：噪音 0 条。
- 全链路实测（`tools/_read_end_to_end.py`，632×632 存盘地图截图，不走游戏窗口）：
  `读取全链路 57.1 s`，8 只怪 / 7 个资源落地，`Event loop is closed` 0 条。

### 10.2 `sprite` 在没有抠图模型的机器上会卡死（**已修**）

本机没有 `~/.u2net/u2net.onnx`，`rembg.new_session("u2net")` 于是**去下载 ~176 MB**，
而这里下不动：实测调用 sprite 之后 5 分钟一点动静都没有 —— 用户看到的就是
「点了读怪物，界面没反应」。`u2netp`（4.7 MB）也一样下不动，`~/.u2net` 始终没建出来。

- 修法：`icons._model_ready()` 先看模型在不在；不在就直接返回纯裁剪
  （`agent.cutout_no_model` 会记一条日志），**按钮不触发下载**。
- 实测：`look` 0.01 s、`sprite` 从「卡 5 分钟以上」变成 0.02 s。
- 副作用（要说清楚）：现在图标是**带底纹的原始格子图**（没有抠背景）。
  想要干净抠图，把 `u2net.onnx` 放进 `C:\Users\87790\.u2net\` 即可，代码不用改。

### 10.3 `collect_icons` 一直静默返回空（**已修**）

`icons.py` 里用了 `json.loads` 却没 `import json`。`NameError` 被
`except Exception` 吞掉 → 所有 function_call 的参数都当成 `{}` → 名字映射永远为空
→ **真机上读多久手册都拿不到一个图标**，而单测是绿的（那条测试把 `collect_icons`
整个换成了假函数）。实测日志：`agent.collect_icons {"names": []}`，
修完变成 5 个名字。

- 修法：补 `import json`；`collect_icons` 加了两个不联网的单测
  （`CollectIconsTest`：能按 name 映射到图片、`look` 那种没有 name 的调用不能算图标）。

### 10.4 还有两笔账，等 owner 点头（**没动代码**）

一、`look`/`sprite` 的次数没有上限。地图三问实测 7 次 look ≈ 45 s（单轮只要 1-2 s，
每次 look 就是一次往返）；手册提示词写的是「不满意就重新裁，**直到你自己看着满意为止**」。

| 方案 | 做法 | 预期 |
|---|---|---|
| A | 地图三问不许 `look`（只给手册留 sprite），看不清写 `???` | 5 s 内读完 |
| B | 每问最多 1 次 `look`；手册整页最多 3 次 look、每只怪 1 次 sprite | 约 12-20 s |
| C | 保持现状（读怪物 55.6 s） | 40-60 s |

二、图标来源：现在用模型裁出来的格子图（带底纹）。`assets/monster_icons/` 里已经有
127 张干净的手册同款缩略图，按名字能命中大部分怪 —— 要不要「书里有图就用书里的、
没有再退回 AI 裁的」？这条会改用户看到的图，所以先问。




## 11. 代码卫生（2026-10-26）

审计工具：`tools/dead_code.py`（只报不改）。它把"全仓库没人引用"和"只有测试在引用"分两类列，
QML 也算产品代码 —— 一堆槽只有界面在调，漏算 QML 会把活函数报成死函数。

**这次真删掉的（全是转发函数/没人调的老壳，删完 345 条测试全绿）：**

| 删了什么 | 在哪 | 为什么 |
|---|---|---|
| `_public_fields` | `chaita/game/read.py` | 去内部字段的逻辑已经搬进 `agent/chat._public`，这份没人调 |
| `_items_dir` / `_item_icon_map` / `_item_icon_exists` / `save_item_icon_map` | `chaita/game/read.py` | 只是转发到 `game/iteminfo`；界面直接调 iteminfo，这层壳没人用了 |
| `FakeResponse` / `fake_urlopen` | `tests/test_read.py` | 上一版桩留下的死代码，连 `io`/`json` 两个 import 一起清掉 |

顺带把 `tests/test_unit.py::ItemIconTest` 和 `tests/test_integration.py::IconChoiceTest`
里对那几个转发壳的调用改成直接打 `iteminfo`（和界面现在走的是同一个入口）。

**还没清、等 owner 一句话的（删了会动界面路径，我不敢顺手）：**

这 11 个 `@Slot` 现在**没有任何地方在调**（QML 扫过、Python 也扫过）：
`addItem`、`addMonster`、`saveItem`、`saveItemFull`、`saveFloorMonsterFull`、
`itemIconChoices`、`libraryChoices`、`setItemIcon`、`clearMaps`、`clearMonsters`、
`cancelSizeAnim`。其中 `clearMaps` / `clearMonsters` 大概率是**「清空」按钮删掉**之后
失去调用的（owner 自己要求删的），其余几个像是旧弹窗/旧编辑路径的壳。

> 注意：`saveItem`/`saveItemFull`/`saveFloorMonsterFull` 这类"保存整条"的槽虽然没人调，
> 但 QML 里在用的是 `saveItemField` / `saveFloorMonsterField`（逐字段保存）。
> 真删之前要再确认一次有没有 `win.xxx` 这种间接调用。

**拆分脚本现在可以复现了**：`tools/_split_overlay.py` 的输入改成 `--from`
（默认 `logs/backup/overlay_before_split_2026.py`），拿现在的门面当输入会**明确报错退出**
（`这个文件里没有 OVERLAY_QML…`），不会悄悄生成一堆错文件。干跑一遍的输出和
第 9 节那张表对得上（reading 648 / monsters 442 / floors 588 / status 105 / chat 57 /
base 398 / startup 119）。

## 12. 覆盖率与"被 try/except 吞掉的 bug"（2026-10-26）

### 12.1 覆盖率工具本身先修了

`tools/coverage_report.py` 以前 `SRC = ROOT`，把 `logs/` 里那份 8384 行的旧备份也算进分母，
覆盖率被稀释成 **6.8%**（4213/61761），看着像没人写测试。收回到 `chaita/` 之后：

```
84.7%  2469/2914   ← 修好统计范围时的真实值
87.0%  2534/2914   ← 补完这一批测试之后
```

补的测试（+38 条，345 → 383）：

| 文件 | 补了什么 |
|---|---|
| `tests/test_capture.py`（新） | 该读哪座塔（前台优先 / 只有一座时兜底 / 两座都开 + 不知道前台就不读）、失败提示里有没有前台进程名和"同时开着 N 个" |
| `tests/test_startup.py`（新） | 崩溃日志真的交给了 faulthandler、handle 没被回收、`app.start` 记下了 qt 版本、`CHAITA_RENDER=software` 真的改了环境变量、收尾顺序（关线程 → 关窗口 → 断 QML → 断 controller）以及"中间一步抛错也要继续拆" |
| `tests/test_ui_library.py`（新） | 模板库读 SQLite（数字转字符串、aliases 解析、坏 JSON 不炸、没名字的行丢掉）、没有库时退回 json、技能串/技能 JSON 两种格式 |
| `tests/test_agent.py`（补） | `look`/`sprite` 两个工具的返回形状（成功=一句说明+一张图；框不合法=只回一句纠正话）、`read` 关掉 items/monsters 时少问一句、`classify` 的三种回答 |

### 12.2 顺手抓到一个真 bug：崩溃日志其实一直没开

`chaita/ui/startup.py` 拆出来的时候漏了两个名字（`_LOGS` 和 `qVersion`），而这两个函数
**整段包在 `try/except: pass` 里**：

```python
try:
    handle = open(os.path.join(_LOGS, "crash.log"), ...)   # NameError: _LOGS 没导入
    faulthandler.enable(file=handle, all_threads=True)
except Exception:
    pass                                                  # 被吞掉，什么都没发生
```

后果：**crash.log 永远是 0 字节**，看起来像"从没崩过"，其实崩溃日志根本没启用；
`app.start`（qt 版本 / 渲染后端）那条启动记录也再没写过一条（实测 `app.start` 行数 = 0）。

- 修法：`from .constants import ... _LOGS`、`from PySide6.QtCore import qVersion`。
- 证据：修完真启动一次（`tools/smoke_close.py 6`），日志里出现
  `2026-10-26 03:26:56  app.start  {"qt_version": "6.11.2", "render": "auto"}`；
  崩溃日志文件被 faulthandler 打开（0 字节 = 没有崩溃输出）。
- 守住它的测试：`tests/test_startup.py::CrashLogTest`（faulthandler 必须被调用、文件名
  必须是 `logs/crash.log`、handle 必须留住）和 `RenderBackendTest`（`app.start` 必须记下
  `qt_version`）。

> 教训：`try/except: pass` 包住的代码，**必须有测试证明它真的做了事**，否则它就是一段
> "看起来存在、实际永远不执行"的代码。

### 12.3 这一批做完后还剩下的低覆盖地方（都不影响现有功能）

| 文件 | 覆盖率 | 为什么低 |
|---|---|---|
| `chaita/game/read.py` | 63.8% | 老读者（`read_items` / `read_floor_monsters` / `read_person`）现在只在"扫描任务""更新状态"这两条支路里用，测试用桩把整条支路替掉了 |
| `chaita/game/agent/icons.py` | 62.6% | rembg 会话创建 / 真实抠图分支：这台机器上模型下不来，跑不到 |
| `chaita/ui/startup.py` | 66.0% | `main()` 里建 QGuiApplication、loadData、装事件过滤器这些必须在真窗口里跑（靠 `tools/smoke_close.py`） |

## 13. 「更新」和「读取」的并行是假的（已修）（2026-10-26）

### 13.1 假并行

`read.py` 里两处都写着"并行跑，串着等会把时间翻倍"，代码却是：

```python
helper = threading.Thread(target=_grab_status_extra)
helper.start()
helper.join()          # ← 紧跟着 join，等于串行
```

- `read_person`（界面状态区那个 ↻ = 「更新」）：先 `read_status` 再 `read_status_extra`，
  两次往返相加。
- `read.read`：地图会话 → 状态 → 附加字段，三次相加。

修法：两问各自起线程、**在一起等**；`read.read` 里状态两问在地图会话**之前**起跑、
地图回来之后再 join（状态那两问比地图快得多，全程躲在地图下面）。

- 守住它的测试：`tests/test_read_parallel.py` —— 用 `threading.Event` 互相等待，
  串行的话第一问会一直等到超时、断言失败（不是靠"跑一遍看起来快"来判断）。
- 实测「更新」（`tools/_update_live.py`，2217×1362 存盘截图）：
  **25.1 s → 16.5 s**，读出来的值完全一样（floor 通天塔 1 层 / hp 300 / atk 15 / def 5）。

### 13.2 修完之后，读取的账变成这样

同一条全链路（`tools/_read_end_to_end.py`）从 57.1 s 变成 77.6 s —— 但这个数字**不是并行退步**，
日志能一项项对出来：

```
03:50:01  agent.reply  ask        2.3 s   ← 状态一问（躲在地图下面）
03:50:04  agent.reply  ask        5.7 s   ← 附加字段（同样躲着）
03:50:02  agent.reply  map_floor  3.3 s
03:50:57  agent.reply  map_mons  55.2 s   ← 3 次 look
03:51:16  agent.reply  map_items 18.7 s
03:51:16  agent.map_done          77.5 s   ← 总时间 = 地图会话，状态两问没再额外加时
```

（上一轮那条 57.1 s 里 `map_mons` 只花了 22.7 s，同一套代码、同一类输入，差别全在
"模型这轮调了几次 look"。）

**结论：现在「读取」的耗时 100% 由地图会话决定，而地图会话由 look 次数决定。**
这就是第 10.4 节那笔账：不砍 look，怎么优化代码都不会低于 40 秒。

### 13.3 已知软点（没改，先记着）

- `read_gem_attributes` 只校验"颜色"不校验"属性值"：模型若回 `{"黄":"乱写"}`，界面上会出现
  「乱写+1」。不硬编码成"攻击/防御/魔防"是因为别的塔可能有生命/魔法这类属性，
  写死会把它们吞掉。测试里把这条真实行为钉住了（`test_parses_and_caches`），
  真要收紧得先知道两座塔各自可能有哪些属性。
- `read_items` 里两个资源类别 + 宝石属性问是三条线程并行，但它没有超时：模型不回就一直等
  （代码注释说这是刻意的：掐断会整类丢结果）。所以资源读取在界面上是"后台慢慢补"，
  不该挡住主流程。

### 13.4 这一轮的覆盖率

```
87.0% → 89.7%（2614/2914）      399 条测试（383 → 399）
新增 tests/test_read_items.py    16 条：资源归一化、宝石属性缓存、read_items 合并、
                                        focus_map 缩放、本层怪转发
新增 tests/test_read_parallel.py  3 条：两条支路真的并行
```

剩下的低覆盖：`agent/icons.py` 62.6%（rembg 真实抠图分支，本机下不到模型）、
`ui/startup.py` 66.0%（`main()` 需要真窗口，靠 `tools/smoke_close.py`）、
`trace.py` 80%、`toolkit/state.py` 81.7%。

## 14. 「↻」实测 + 工具输出编码（2026-10-26）

### 14.1 ↻ 这条路验过了

界面上的「↻」（某层行尾）走的是：磁盘上那层的地图截图 → `read_floor_monsters`
→ `agent.map.monsters(image, known=手册里的怪名)`。以前只有桩测试，这一轮拿存盘截图实测：

```
样图 632×632，已知怪 3 只
↻ 33.6 s，3 条
  红史莱姆 ×6   绿史莱姆 ×6   骷髅人 ×2
```

同一次调用在 trace 里也留了证据（另一次跑）：`agent.map_mons {"count": 3, "known": 3,
"seconds": 17.9}`。两次差一倍是同一个老问题：模型这轮调几次 look。

### 14.2 工具自己把输出截断了（已修）

`tools/_refresh_live.py` 打印 `↻` 时撞上中文控制台的 GBK 编码：`UnicodeEncodeError`
抛在 stderr（被我重定向丢了），stdout 只剩第一行，**退出码还是 0** —— 看起来像
"工具没跑完"。已经给 5 个"只读磁盘截图"的校验工具统一把 stdout 固定成 UTF-8：

`tools/_refresh_live.py`、`tools/_read_end_to_end.py`、`tools/_time_manual.py`、
`tools/check_chat.py`、`tools/check_session_loop.py`

（`tools/test_ui_synthetic.py` 之前也踩过一次同一个坑，那次修的是检查项名字里带 `✕`。）

> 教训：工具的输出编码和功能一样要测。带符号的 print 遇到 GBK 会静默半途而废。

### 14.3 覆盖率 89.7% → 90.5%（2643/2922）

```
+6   tests/test_trace.py         日志真写进文件、字段是 JSON、不可序列化的值兜住、
                                 超 2 MB 轮转成 .1、写不进去也不抛
+16  tests/test_toolkit_state.py 上次记录的截断（怪 200 / 层 50）、坏行丢掉、
                                 截图没了就清空 url、`CHAITA_NO_UI_STATE` 时不动状态文件、
                                 几何夹到屏幕内、`_apply_ui_state` 六个属性都写、
                                 `_place_right` 贴右缘 / 太高的窗口自动压矮
```

现在最底的三个是：`agent/icons.py` 62.6%（rembg 真实抠图分支，本机下不到模型）、
`ui/startup.py` 66.0%（`main()` 要真窗口，靠 `tools/smoke_close.py`）、
`config.py` 85.0%。

## 15. 线程收尾与配置/资源表（2026-10-26）

### 15.1 地图那一问炸了，状态两个线程也得收回来（已修）

第 13 节把状态两问改成和地图会话并行之后留了个尾巴：如果 `_map.read` 抛异常，
`read()` 会直接往上抛，**两个后台线程还在跑**——它们跑完把结果写进已经没人看的 `box`，
重试一次就多两个无主请求（还占着 API 配额）。线程里抛的异常也没人接，
pythonw 下连 stderr 都没有，等于静默丢失。

修法：

- `try: opened = _map.read(...) finally: 把两个线程 join 完`；
- 两个线程各自 `try/except`，异常记进 `failure` 字典，回来补一条
  `read.status_failed` 日志（不再消失）；
- 状态那两问失败**不影响**地图结果落地（层号、怪、资源照常返回）。

守住它的测试（`tests/test_read_parallel.py`，现在 5 条）：

- `test_map_failure_still_joins_status_threads`：地图抛错时，两个线程都必须**跑完**（用
  两个带 sleep 的桩 + 记录列表验），否则那个 `finally` 就是假的；
- `test_status_failure_does_not_lose_map_result`：两问都炸，`read()` 仍然返回层号和怪。

### 15.2 配置和资源表也补上测试

| 文件 | 新测试 | 钉住什么 |
|---|---|---|
| `tests/test_config_iteminfo.py` | 15 条 | API key 来源优先级（环境变量 > `config.yaml` 的 `api_key` 行 > 空串）、引号/空格/注释行、文件不存在；资源图标"颜色 + 种类"规则、用户映射优先且映射到不存在的图时退回规则、`effect_for` 按图标/按名字查表、`normalize_effect` 规整、`choices()` 把血瓶合并成一条、道具表缺失时仍列出用户配过的图 |
| `tests/test_read_parallel.py` | +2 条 | 见 15.1 |

写这些测试时踩到两个"我以为是 A、其实是 B"的地方，顺手记下来（都是**现存行为**，不是 bug）：

- 图标规则里蓝色映射到 `purple`（`蓝宝石 → gem_purple`），不是 `gem_blue`；
- `choices()` 不是"只读道具表"：`assets/items/map.json` 里用户配过的图标也会列出来，
  所以"表没了但 map.json 还在"时列表**不是空的**。

### 15.3 覆盖率 90.5% → 90.8%（2659/2929，441 条测试）

现在最低的只剩三个，而且都有明确原因：

| 文件 | 覆盖率 | 原因 |
|---|---|---|
| `agent/icons.py` | 62.6% | rembg 真实抠图分支：本机下不到 u2net 模型，`_cutout` 直接走纯裁剪 |
| `ui/startup.py` | 66.0% | `main()` 要真窗口（建 QGuiApplication、loadData、装事件过滤器），靠 `tools/smoke_close.py` |
| `controller/floors.py` | 86.5% | 「这一层」弹窗那批逐字段保存的边界，界面自检覆盖了主路径 |

## 16. 三条"只在真机上才验得了"的路径（2026-10-26）

这一轮没改产品代码，把三件一直"只有单测、没在真程序上走过"的事走了一遍。

### 16.1 软件渲染逃生口（`CHAITA_RENDER=software`）

给什么用：这台机器出现过 GPU 层 LiveKernelEvent 和「该内存不能为 read」的闪退，
`_render_backend_hint()` 留了一个"绕开显卡驱动"的开关（`QT_QUICK_BACKEND=software`）。
以前只测过"环境变量被设上了"，没测过"真开得起来"。

```
python tools/smoke_close.py 6 --software
窗口: [(35719586, 'ChaitaAssistant', 'Qt6112QWindowToolSaveBits')]
退出码: 0     logs/crash.log 0 字节
app.start {"qt_version": "6.11.2", "render": "software"}
```

结论：逃生口能用（窗口真的出来了、真的关干净了、日志记的是 software）。

### 16.2 首次启动（`logs/` 下什么都没有）

把 `ui_state.json` 和 `last_session.json` 先挪走，再真启动一次：

- 窗口照样出来、关得干净（退出码 0、crash.log 0 字节）；
- 关窗时**自己写出**了 `logs/ui_state.json`（64 字节）：`x=1343 y=24 340×712`
  —— 1920 宽屏幕上就是"贴右缘、上边留 24"，正是 `_place_right` 的预期；
- `last_session.json` **没有**被创建：这次没有记录任何怪/层，空的话不该落文件（对）；
- 验完把用户原来的窗口位置（`x=10 y=20`）恢复回去了。

对应测试补了两条（`tests/test_toolkit_state.py`，现在 18 条）：
`test_first_run_has_no_state_and_falls_back`（没记录 → `_apply_ui_state` 返回 False →
贴右缘）、`test_close_writes_state_so_next_run_restores`（关窗写盘 → 下次能原样摆回）。

### 16.3 `config.yaml` 里的 key（没有环境变量时）

单测覆盖了"读哪一行"，但没验过"真能拿它发出请求"。这次把 `DEEPSEEK_API_KEY`
从环境里删掉再跑：

```
config.yaml 里读到 key: True 长度 35 开头 sk-b…
对话 3.3 s   改后的 hp: 60   模型说法「生命从 53 改为 60，其余字段保持不变」
```

结论：没设环境变量的用户，只要 `config.yaml` 里有 `api_key` 就能用（`tools/check_chat.py` 是现成的验证脚本）。

### 16.4 还剩什么

产品上只剩三件**等 owner 点头**的（都是你看得见的东西）：

1. `look` 上限：A 地图不许 look（5 s）/ B 每问最多 1 次（12-20 s）/ C 现状（约 50 s）；
2. 图标是否优先用 `assets/monster_icons/` 里 127 张干净同款（现在用 AI 裁的、带底纹）；
3. 11 个没人调的孤儿槽（`addItem` / `addMonster` / `saveItem` / `saveItemFull` /
   `saveFloorMonsterFull` / `itemIconChoices` / `libraryChoices` / `setItemIcon` /
   `clearMaps` / `clearMonsters` / `cancelSizeAnim`）删不删。

除此之外，这条目标里能做的都做完了：结构、三个功能、文档、测试、死代码、真机验证。

## 17. 读地图：名字飘、数量读成效果（都已修）+ look 取舍数据（2026-10-26）

### 17.1 「读地图」的名字每次都不一样（已修）

同一张 632×632 地图截图，**同一套代码**跑两遍，怪名对不上：

```
没有候选名：
  第一次  紫史莱姆、紫色幽灵、红史莱姆、红色幽灵、绿史莱姆、蝙蝠、骷髅人、骷髅战士
  第二次  ???、初级法师、幽灵、红史莱姆、绿史莱姆、蝙蝠、骷髅人、骷髅士兵
  两次一致：4 个共同 / 12 个并集
```

玩家看到的就是"每次读出来的怪都不一样"。根因：地图上怪的小图标只有十几像素，
模型是在**猜**名字；而手册那一栏本来就有准确名字，读地图却没用上（只有行尾的「↻」用了）。

- 修法：`read.read(..., known=[...])` → `map.read(image, known=...)` →
  `monsters_of(session, known)`，控制器把面板里已有的怪名当**候选名字**传进去
  （只传名字，不参与看图、不替模型判断）。
- 实测（`tools/compare_map_stability.py`，同一张图各跑两遍）：**带候选名两次完全一致，
  8 个共同 / 8 个并集**。
- 守住它的测试：`tests/test_agent.py::MapTest::test_known_names_are_passed_as_hint`
  （怪那一问里必须出现候选名）、`test_no_hint_without_known`；
  `tests/test_worker.py::ReadWorkerOnceTest::test_success_map_read`
  （控制器确实把面板里的名字传下去了，空名字要滤掉）。

### 17.2 「血瓶 ×1200」：数量被读成了效果数值（已修）

实测一次读地图拿到 `{"name": "血瓶", "count": 1200}` —— 那是它旁边印的回血量，
不是数量。界面上会显示成「血瓶 ×1200」。

- 修法：`ITEM_QUESTION` 里明确写「count 只放数量（格子角上印的 1~3 位数，通常 1~9）；
  『回血 300』『体力 1200』那类**是效果数值，绝对不要写进 count**」。
- 实测（同一条路径再跑）：`{"name": "血瓶", "count": 6}`（对）。
- 这是**提示词措辞**的修正，不改解析逻辑（解析那边本来就会把非数字丢掉）。

### 17.3 look 的取舍：数据摆出来，等 owner 选

手册页（2582×1390，5 只怪、20 个字段，有手工核对过的真值）：

| 设置 | 耗时 | 命中字段 |
|---|---|---|
| C 现在（提示词只说"最多 3 次"） | 14.0 s | 20/20 |
| B 每只怪 1 次 sprite、整页 1 次 look | 24.7 s | 20/20 |
| A 禁止 look | 13.4 s | 20/20 |

**同一套 C 设置换几轮跑，耗时在 14-56 s 之间飘**（模型自己决定调几次 look），
所以真正的毛病不是"慢"，是"不可预期"。

地图页（632×632）：

| 设置 | 耗时 | 结果 |
|---|---|---|
| C 允许 look | 32.5 s / 79.8 s（两次） | 8-9 条怪，7 条资源 |
| A 禁止 look | 19.6 s / 31.6 s | 6-7 条怪，4 条资源，出现 `???` |

所以：**手册页不要 look 也全对**（A 最快且 20/20）；地图页不要 look 会掉东西（多 `???`）。
如果要一个统一的硬限制，建议按"手册禁止 look、地图每问最多 1 次"来定 —— 但这条
会改读出来的内容，所以等 owner 点头再动。

工具：`tools/compare_look_limits.py`（手册页 A/B/C）、`tools/compare_look_map.py`（地图页）。
两个都是只读磁盘截图、不碰游戏窗口。

## 18. 清掉 7 个"被取代、又没人调"的旧槽（2026-10-26）

`tools/dead_code.py` 早就报出 11 个 `@Slot` 在 QML 和 Python 里都没有调用点。
这一轮逐个看过代码后，**删了 7 个**、**留了 4 个**（都有明确原因，不是漏）。

### 18.1 删掉的（各自被谁取代）

| 删掉的槽 | 现在走谁 | 行为还在不在 |
|---|---|---|
| `addItem` | `addItemFull` | 在（一次把名字/效果/数量/图标都给全） |
| `saveItem` | `saveItemField` | 在（逐字段保存，含空名字=删除） |
| `saveItemFull` | `saveItemField` | 在（资源图现在跟名字自动走，界面没有选图入口） |
| `saveFloorMonsterFull` | `saveFloorMonsterField` + `addFloorMonsterFull` | 在 |
| `addMonster` | `addMonsterTpl` / `saveMonsterFull` | 在（「＋」下拉走模板） |
| `itemIconChoices` | —（资源图标按名字自动取） | 界面本来就没有选图入口 |
| `libraryChoices` | `monsterIconChoices` | 在（怪物编辑器只列 monster 分类） |

一共删掉约 150 行控制器代码，`metaObject().methodCount()` 从 77 降到 70，
`propertyCount` 仍是 26（属性没动）。

### 18.2 留着的 4 个（原因写在 docstring 里）

- `setItemIcon`：代码里原话写着"**界面不再提供入口**……留着是给后续素材库纠错用的接口"。
- `cancelSizeAnim`：`animateSize` 的配套，测试用它让动画停下来。
- `clearMaps` / `clearMonsters`：「清空」按钮是 owner 要求删的，但
  "地图被清空时「这一层」弹窗要收起"这条行为还靠 `clearMaps` 触发，测试也拿它整块重置。

### 18.3 顺带发现的一处"台账对不上"

`tests/test_editor.py::SlotSignatureTest.QML_SIGNATURES` 是**手写**的"QML 用到的签名"清单，
里面还列着 `addItem` / `addMonster` / `clearMaps` / `clearMonsters` / `itemIconChoices` /
`libraryChoices` / `saveItem` —— 实际 QML 一个都没调（QML 里真正调的是 55 个名字）。
手写清单会漂；自动的那条 `test_every_qml_call_is_a_slot`（直接扫 QML 正文）才是防线。
这次把 7 条过期项删了。

### 18.4 测试怎么处理（445 → 434 条）

- 只测已删槽的用例整条删掉（`test_add_item` / `test_save_item*` /
  `test_save_floor_monster_full_keeps_old_icon` / `test_add_monster` /
  `test_library_choices` / `test_icon_choices*`）。
- **行为还在的三条改成走新入口**，没有因为删旧槽丢掉覆盖：
  `test_add_save_remove`（`addItemFull` + `saveItemField`）、
  `test_empty_name_removes`（`saveItemField(name, 空)`）、
  `test_done_survives_save_full`（`saveFloorMonsterField` 之后勾选不丢）、
  以及集成测试里三条 `addMonster` → `addMonsterTpl`。

### 18.5 一个"看着该删、其实还有独有行为"的

`saveFloorMonster` 现在也没有调用点了，但它和 `saveFloorMonsterField` **不完全等价**：
它改名之后会**按名字重排**（`saveFloorMonsterField` 只改字段、不排序），
`tests/test_integration.py::test_save_floor_monster_rename_keeps_sorted` 守的就是这一点。
所以先留着 —— 如果确定行内改名这条 UI 以后都不用，再连它一起删。

### 18.6 验收

```
Ran 434 tests in 56.8s   OK        界面自检 全部通过（exit 0）
真启动真关窗 退出码 0  crash.log 0 字节
覆盖率 90.8% → 91.4%（2595/2839，分母变小是因为死代码被删了）
死代码审计：全仓库没人引用 0 个
```

## 19. 文档对齐（2026-10-26）

这一轮没动代码，把三份文档里"和现在的事实不符"的地方逐条改掉 ——
过期的文档比没有文档更害人，下一个接手的人会照着错的做。

### 19.1 `SOFTWARE_DESIGN.md`

| 位置 | 原来写的 | 现在（实测） |
|---|---|---|
| §12 单次延迟 | "2~5 秒" | 一次往返 **1.7~2.3 秒**（关思考） |
| §12 新增行 | — | 连问三句不崩、读怪物 21.5~55.6 s、读地图 32.5~79.8 s、对话 3.0~3.3 s、名字一致率 8/8（加候选名）/ 4-12（不加） |
| §13 已知限制 | 5 条旧条目 | 8 条：`look` 无硬上限、抠图要 u2net 模型（本机没有 → 图标带底纹）、单实例保护未做（代码里确实没有任何互斥）、候选名的副作用…… |
| §11 思考 token | "max_tokens 1200 时输出空 → 放到 3000" | 预算 12000 **且直接关掉 thinking**：58~135 秒 → 1~3 秒 |
| §11 新增三条坑 | — | 会话每次 `asyncio.run()` 第二句必崩；`try/except: pass` 里的代码写错只静默失效（崩溃日志那次的教训）；手写的 QML 签名台账会漂 |

### 19.2 `DESIGN.md`

第 6 节「落地状态」的三项验证数字是旧的，按刚实测的改了：

```
unittest            340 项  →  434 项
test_ui_synthetic   256 项  →   56 项（PASS 行数实测）
check_scenarios      31 个  →   32 个（全部 OK、warnings=0）
```

另外两处还写着「清空」按钮（分区头、改前/改后那段），按 owner 要求删掉之后
这个按钮已经不存在了，改成「＋ 加怪 / 读怪物 / 读地图」并注明「清空」是按要求删掉的。

### 19.3 验收

```
Ran 434 tests in 56.6s   OK
tools/test_ui_synthetic.py   56 项全 PASS（exit 0）
tools/check_scenarios.py     32 个场景全部 OK、warnings=0（exit 0）
```

这一轮之后，代码、测试、三份文档三者对得上；产品上只剩两件等 owner 决策的
（`look` 上限、图标来源），其它都做完了。

## 20. 单实例保护（2026-10-26）

「已知限制」里挂着一条：**连点两次启动器会叠出两个悬浮层**。这一轮先复现、再修。

### 20.1 复现（`tools/check_single_instance.py`）

真开两个 `run.py`，数标题为 ChaitaAssistant 的可见窗口：

```
第一个进程 pid=30996，第二个 pid=53916
活着的进程： [30996, 53916]
悬浮层窗口数： 2          ← 两个都盖在游戏上、都去抓图，用户分不清点哪个
退出码： 0 0
```

### 20.2 修法

`startup.main()` 第一件事先抢 `logs/app.lock`（`QLockFile`）：

- 抢不到 → 打印「拆塔辅助已经开着了」并 `return 0`（**不建窗口**，所以不会闪一下）；
- `staleLockTime = 0`：锁里记 PID，进程崩了留下的死锁会被下一次启动接管，
  不会把用户永久挡在门外；
- `_run()` 外面包 `try/finally`，正常退出时 `unlock()`（锁文件也会被删掉）。

### 20.3 复测

```
第一个进程 pid=42948，第二个 pid=57408
活着的进程： [42948]                 ← 第二个当场退出
悬浮层窗口数： 1
退出码： 0 0
```

再跑一次 `tools/smoke_close.py 6`：退出码 0、`app.start` 正常记录、`crash.log` 0 字节，
说明"退出→锁释放→下次还能开"这条也通。

### 20.4 测试（+3 条）

`tests/test_startup.py::SingleInstanceTest`：

- `test_second_instance_is_refused`：第二个必须被拒绝，锁文件确实存在；
- `test_release_allows_next_start`：退出后要能再开（不然用户关了就再也打不开）；
- `test_stale_lock_from_dead_process_is_taken_over`：手写一个"死进程的锁"，
  下一次启动必须能接管。

### 20.5 验收

```
Ran 437 tests in 55.4s   OK        界面自检 全部通过（exit 0）
连开两次 → 1 个窗口        真启动真关窗 退出码 0  crash.log 0 字节
```

## 21. 给 look / sprite 加硬上限（兜底，不是取舍）（2026-10-26）

第 10.4 节挂着"look 次数没有硬上限，要不要砍"这笔账 —— 那是**质量取舍**，等 owner 定。
这里做的是另一件事：**兜住病态循环**。两者不冲突：

- 正常一次读，实测最多用 3 次 look / 每只怪 1-2 次 sprite，新上限（look 6 次、
  每只怪 sprite 3 次）**碰都不碰**，所以读出来的东西和以前完全一样；
- 上限只在模型钻牛角尖时生效，把"7 分钟不返回"变成"最多几个回合就收口"。

### 21.1 证据：同一张缩略图，以前跑不完、现在 67 秒出结果

那张 900×484 的手册缩略图（手册区只占画面一小块）实测会把模型带进死循环：
连调 **17 次 look** 仍不收敛，7 分钟没有返回，我只能手动掐掉。

加上限后（`tools/` 里没有专门脚本，直接跑 `agent.monster.read`）：

```
样图 (484, 900, 3)
读怪物 67.4 s，6 行
   绿色史莱姆 100 25 5 1 图      红色史莱姆 120 28 6 1 图
   小蝙蝠 85 42 3 1 图           初级法师 95 42 3 2 图
   骷髅士兵 140 38 11 2 图       黑色史莱姆 175 44 7 3 图
agent.collect_icons {"names": [6 只]}
agent.manual_done {"count": 6, "icons": 6, "seconds": 67.4}
```

同一时间窗里的工具调用（日志数出来的）：`look` 成功 6 次、**撞上限 3 次**、
`sprite` 成功 12 次、撞上限 0 次 —— 上限确实拦住了模型继续放大。

### 21.2 实现

- `icons.look_tool(image, limit=6)`：第 7 次起不再给图，只回一句
  「本次已经看了 6 块……按你已经看到的内容直接作答，看不清写 ???」，
  日志记 `agent.look_capped`。
- `icons.sprite_tool(image, per_name=3)`：同一只怪第 4 次起不再重抠，
  只回「这张图已经抠过 3 次了，就用你拿到的那张，接着处理下一只」，
  日志记 `agent.sprite_capped`。
- 手册提示词同步改成「**不满意可以调一次坐标重裁**；同一只怪最多试 3 次」——
  原来写的是"直到你自己看着满意为止"，等于鼓励无限重试。

### 21.3 测试（+2 条）

`tests/test_agent.py::IconToolsTest`：
`test_look_has_a_hard_cap`（第 3 次起只回文字、不再带图）、
`test_sprite_has_a_per_monster_cap`（同一只怪第 2 次起拒绝，换一只怪还能抠）。

### 21.4 验收

```
Ran 439 tests in 59.0s   OK        界面自检 全部通过（exit 0）
真启动真关窗 退出码 0  crash.log 0 字节
病态缩略图：7 分钟不返回 → 67.4 秒、6 行、6 张图（look 撞上限 3 次）
```

## 22. 图标来源：把两个方案摆在一起看了（2026-10-26）

第 10.4 节挂着"图标要不要优先用 `assets/monster_icons/` 里那 127 张干净同款"。
这一轮不猜了，直接做了一张对比图（`tools/compare_icons.py` →
`docs/capture/_icon_compare.png`，我看过图）：

```
样图 docs/capture/_manual_repro.png（通天塔1，五只怪）
  红头怪    AI 有 157×139   素材库 没有同款
  骷髅人    AI 有 157×139   素材库 没有同款
  小蝙蝠    AI 有 157×139   素材库 没有同款
  青头怪    AI 有 157×139   素材库 没有同款
  大蝙蝠    AI 有 157×146   素材库 有 26×25
素材库可查的图标名：103 个
```

**结论（两张图摆一起就能看出来）：**

1. **命中率很低**：这一页 5 只怪只有 1 只在库里。库是从两座塔的
   `project/materials` 切的，名字是那两座塔的叫法；这本手册的怪名对不上。
2. **对上了的那一只更小**：库里 `26×25`，AI 裁的 `157×146`。界面上是按原始像素
   贴的（不放大），换成库里的那只就等于把图标缩到 1/6。
3. AI 裁的这张**带手册底纹**（因为本机没有 u2net 模型，`sprite` 退化成纯裁剪）。

所以「优先用书里的同款」这条对现在这本手册**基本没有收益**，反而可能更糊。
**建议不做**；真正能让图标变干净的是把 `u2net.onnx` 放进 `~/.u2net`（代码不用改）。

### 22.1 顺带量到的一个数

这次读（五只怪）用了 **108.4 秒**，`agent.manual_done {"count": 5, "icons": 5}`。
上限现在是 look 6 / 每只怪 sprite 3；5 只怪最多 15 次 sprite ≈ 20 个回合，
所以还是能到 100 秒级。要更快就把 `per_name` 收到 2（上限 10 次），
但那属于"读得更急、可能少一次重裁"的取舍，等 owner 一句话。

### 22.2 验收

```
tools/compare_icons.py  exit 0，出图 docs/capture/_icon_compare.png（240×600）
看图的判断：左列 AI 裁的（带底纹、大）／右列只有一只（透明、26×25）
```

## 23. README 重写（2026-10-26）

README 是任何人打开仓库看到的第一页，而它停在"四个功能之前"的年代：

| 原来 | 实际 |
|---|---|
| "点一下「读取」，显示人物当前状态和**当前地图截图**" | 现在是**三个功能**：读怪物手册 / 读地图 / 对话 |
| "不做的事：逐格识别、认怪物、算伤害、求路线" | 认怪物已经做了（读怪物手册）；不算伤害这条不变，仍写在最上面 |
| `src/chaita/ui/main.py`（QML 内嵌在里） | `chaita/ui/qml/MainWindow.qml` 单独一份；`src/` 这一级已经删了 |
| 依赖只列 PySide6/OpenCV/numpy/pywin32/dxcam | 还要 `agent_framework` + `openai`；`rembg`/`onnxruntime` 是可选的（抠图用） |
| "等 2～5 秒" | 实测：一次往返 1.7~2.3 s、对话 3 s、读怪物 21~110 s、读地图 32~80 s |
| 已知限制里写着"没有单实例保护，连点两次会开两个悬浮层" | 已经做了（第 20 节） |
| 没有提 `logs/` | 补上：出问题先看 `logs/chaita.log`，崩溃看 `logs/crash.log` |

新版按"三个功能 → 怎么装怎么配 → 怎么用（含 ↻ / 备忘 / 勾选）→ 多久能出结果 →
图标为什么会带底纹 → 文件结构 → 已知限制 → 它到底怎么工作"重排，150 行。

### 23.1 顺带修掉一处文档里的红线冲突

`SOFTWARE_DESIGN.md` 的「后续可能的方向」里原本列着 **"伤害与临界值计算"** ——
这和 owner 定的红线（工具只给信息、不算结论）直接冲突，已经删掉并注明原因。
同一节里"打包成 exe"指向的 `overlay.py`（`sys.prefix` 那段）也改了指向：
那段现在在 `chaita/ui/__init__.py`。

### 23.2 验收

```
README 里 `src/chaita` / "QML 内嵌" 的过期引用：0 处
三个功能都写到；单实例、logs、图标三种状态（AI 裁 / 库图 / u2net 抠图）都写明
```

（这轮只改文档，代码没动；测试与上一轮一致：439 条全过。）

## 24. 安装清单漏了一个包（2026-10-26）

这是"按 README 装一遍"才会暴露的问题：仓库里的测试全绿（本机早就装好了），
但**照 `environment.yml` 建出来的新环境跑不了「读取」**。

### 24.1 事实

```
pip show agent-framework        → Requires: agent-framework-core        ← 只有 core
pip show agent-framework-openai → Requires: agent-framework-core, openai
```

代码里用的是 `from agent_framework.openai import OpenAIChatClient`，
也就是说需要 `agent-framework-openai` 这个**单独的包**。
而 `environment.yml` 的 pip 段原来只写了 `agent-framework` —— 装完一 import 就
`ModuleNotFoundError: No module named 'agent_framework.openai'`。

### 24.2 修法

`environment.yml` 的 pip 段改成：

```yaml
      - agent-framework>=1.22
      - agent-framework-openai>=1.17
      - openai>=3.35
      # 可选（抠图用，不带也能跑）
      # - rembg>=2.0
      # - onnxruntime>=1.31
```

### 24.3 加了两个护栏

- `tools/check_deps.py`：拿 AST 扫 `chaita/` 和 `run.py` 里的第三方 import，
  逐个映射到发行包名（**会区分子模块**：`agent_framework.openai` 要的是
  `agent-framework-openai`），再跟 `environment.yml` 对齐。
  实测现在就报得出问题（修之前输出 `!! environment.yml 缺：agent-framework-openai`）。
- `tests/test_deps.py`（2 条）：一条跑上面那个检查必须 exit 0；一条用 PyYAML
  解析 `environment.yml`（没装 pyyaml 就 skip），确认 pip 段里确实有
  `agent-framework-openai`。

### 24.4 验收

```
tools/check_deps.py  → OK：必需的包都在 environment.yml 里（exit 0）
YAML 解析 ok；pip 段: dxcam>=0.3.0 / agent-framework>=1.22 /
                     agent-framework-openai>=1.17 / openai>=3.35
Ran 441 tests   OK（439 → 441）
```

README 的「装」也补了一句：这两个包是什么关系、漏了会怎样、怎么自查。

## 25. 工具脚本体检 + 去掉没用到的依赖（2026-10-26）

改造过程里删过 `src/` 这一级和 `agent_read.py`，**工具脚本最容易悄悄烂在那儿**：
平时不跑，等要用的时候才 ImportError。这一轮做了两件事。

### 25.1 `tools/check_tools.py`（静态体检，46 个脚本）

扫每个脚本的 import 和文本，查三种问题：

- 引用了已经不存在的模块（`chaita.game.agent_read` 之类）；
- 文本里还留着 `src/chaita` 这种旧路径；
- 语法层面读不开（实测撞到一个：`tools/test_click.py` 带 UTF-8 BOM，
  `ast.parse` 按 utf-8 读会报 "invalid non-printable character" —— 改成
  `utf-8-sig` 读就好；脚本本身 Python 能跑，不用改内容）。

第一版把**检查脚本自己**也报了（它带着"已删模块"常量表），已排除。
现在结果：`OK：没有指向已删模块/旧路径的引用，import 都能解析`。

### 25.2 删掉 `dxcam`

`environment.yml` 的 pip 段还背着 `dxcam` —— 但全仓库**没有任何地方 import 它**
（抓图早就是 `PrintWindow`，`SOFTWARE_DESIGN` §5 里它只是"被否掉的方案"那一列）。
没用的依赖留着只会让新环境装得更慢、更难装。

现在 pip 段只有三个必需的：`agent-framework` / `agent-framework-openai` / `openai`
（抠图那两个 `rembg` / `onnxruntime` 以注释形式留作可选项）。

### 25.3 护栏

`tests/test_tools.py`（1 条）：跑 `tools/check_tools.py` 必须 exit 0。
加上上一轮的 `tests/test_deps.py`，现在"安装清单"和"工具脚本"两处都会自动对账。

### 25.4 验收

```
tools/check_tools.py → 检查了 46 个工具脚本 / OK（exit 0）
tools/check_deps.py  → OK：必需的包都在 environment.yml 里（exit 0）
environment.yml 的 pip 段：agent-framework / agent-framework-openai / openai
Ran 442 tests   OK（441 → 442）
```

## 26. 测试把用户的运行日志清空了（已修）（2026-10-26）

排查"日志怎么只剩 669 字节"时发现的：`logs/chaita.log` 从几万行变成几百字节，
`logs/chaita.log.1` 只剩 85 字节 —— 以前的现场全丢了。

### 26.1 原因

`tests/test_trace.py` 里测"文件超过上限会轮转"那条，把模块级常量
`trace._MAX_BYTES` 改成 **10 字节**，但 tearDown 只还原了日志路径，**没还原这个值**。
于是同一轮测试之后每写一条日志就触发一次轮转：

```python
_MAX_BYTES = 10          # 泄漏到后面所有测试
os.replace(LOG, LOG + ".1")   # 每次 note() 都把真日志挪走、再覆盖 .1
```

后果：真日志被自己"轮转"成一两百字节，出问题再想查就没现场了。
（也解释了为什么有几次我 grep 不到别人跑留下的 `app.start`。）

### 26.2 修法

- tearDown 里连 `_MAX_BYTES` 一起还原（改成三元组保存/还回去）；
- 加一条守门测试 `test_rotation_limit_is_the_real_default`：断言默认值仍然是
  `2 * 1024 * 1024`。轮转那条测试以后要是再忘了还原，这条会立刻红。

### 26.3 实测

```
跑测试前 logs/chaita.log：669 字节（被清空后）
跑完 443 条测试之后：      59917 字节（不再被轮转吃掉）
trace._MAX_BYTES = 2097152（还原成 2 MB）
Ran 443 tests   OK
```

> 诚实说明：**这次改造期间丢掉的日志历史找不回来了**（`_rotate_if_needed`
> 会把 `.1` 覆盖掉，没有第二层备份）。现在这个坑堵上了。

## 27. 测试隔离：两道守门（2026-10-26）

连续两轮踩到"测试污染进程"的坑（第 16 节 `QT_QPA_PLATFORM`、第 26 节
`trace._MAX_BYTES`），这一轮把它变成两条自动检查，而不是靠下次记得。

### 27.1 运行时守门：`tests/test_zz_isolation.py`（5 条）

文件名以 `test_zz_` 开头是**故意的** —— unittest 按文件名字母序执行，它排最后，
所以断言看到的是"整套测试跑完之后"的状态。它在 import 时给这些全局量拍快照：

- 环境变量 `CHAITA_*` / `QT_QPA_PLATFORM` / `QT_QUICK_BACKEND` / `QT_OPENGL` / `U2NET_HOME`；
- `trace._MAX_BYTES` / `trace._LOG_DIR` / `trace._LOG_PATH`；
- `const.SESSION_PATH` / `const.UI_STATE_PATH`；
- `builtins.__import__`、`winutil.find_window`（测试里常用的两个桩点）。

跑完整套之后逐项比对，不一样就红。

### 27.2 import 阶段守门：`tools/check_test_isolation.py`

`test_zz_isolation` 的快照是"所有测试模块都 import 完"之后拍的，**抓不到 import
阶段的污染** —— 而 `QT_QPA_PLATFORM` 那次恰恰是 import 阶段。所以另起一支：

起两个干净子进程，一个只 `import chaita.ui.main`（基线，产品本来就会设
`QT_PLUGIN_PATH` 这类），另一个再 import 全部 `tests/test_*.py`，比对两次的环境变量，
差出来的就是测试自己的污染。

**证明它真管用**（把当年那句污染临时塞回去再撤掉）：

```
塞进污染之后：exit=1
!! QT_QPA_PLATFORM: None → 'offscreen'
还原之后：    exit=0   OK：测试模块 import 没有额外改动环境变量
```

### 27.3 都接进测试

`tests/test_tools.py` 现在两条：工具脚本不许引用已删模块/旧路径；
测试模块 import 不许改环境变量。加上 `test_zz_isolation.py`，一共三道
（运行后 / import 时 / 工具引用），都会被 `unittest discover` 跑到。

### 27.4 验收

```
Ran 449 tests in 56.7s   OK（443 → 449：+5 隔离 +1 import 检查）
tools/check_test_isolation.py → OK（exit 0）
tools/check_tools.py          → 46 个脚本 OK（exit 0）
```

## 28. 补测试 + 「QML 要不要拆」的结论（2026-10-26）

### 28.1 补的 10 条（459 条，覆盖率 91.4%）

`tests/test_winutil_skillinfo.py`：

- `clean_title`：RM 的原生标题、Edge 那种一长串噪音（`坐牢成仙 - HTML5魔塔 和另外
  14 个页面 - 工作 - Microsoft Edge` → `坐牢成仙`）、零宽字符 U+200B、只有噪音的标题。
  这块错了面板上就顶着一串浏览器文字，属于"一眼就能看见"的东西。
- `skillinfo.effect_for / source_for / known`：查得到给原话、带 `[b]` 后缀能剥掉、
  查不到给空串、表文件没了也不炸。真实数据抽查：`先攻 → 怪物首先攻击`，
  塔自加技能（`纳魔为攻`）按设计返回空串。

### 28.2 「QML 还是一个 5226 行的文件」——我看过了，建议**先不拆**

owner 当初那句"为什么所有代码写一个文件里"是针对 Python 的（那时 `overlay.py`
8384 行）。QML 现在仍然是一份 5226 行的 `qml/MainWindow.qml`，所以我认真评估了一遍：

**现状**：里面用 QML 6.5 的 `component` 语法定义了 6 个内联组件
（`CountBadge` / `GhostBtn` / `SectionTitle` / `StatChip` / `ThinBar` / `LabeledField`），
其余都是根 `Window` 的一整棵树。

**拆成 `components/*.qml` 的硬阻塞**：

1. 这些组件都直接用根节点上的 `theme.xxx`（字号/颜色的令牌）和 `win.xxx`（界面状态）。
   换成独立文件后，它们看不到根节点 —— 必须先把 `theme` 做成 `pragma Singleton`
   （要配 `qmldir` + 注册导入路径），`win` 那些状态则要改成显式属性传进去。
   这不是"剪切粘贴"，是把 6 个组件的接口全部重新定义。
2. 现在 QML 是用 `engine.loadData(OVERLAY_QML, QUrl("qrc:/MainWindow.qml"))` 加载的字符串，
   **相对导入解析不到磁盘目录**。要拆文件就得把基准 URL 改成
   `QUrl.fromLocalFile(.../MainWindow.qml)`，并且 `tools/preview_overlay.py`、
   `test_ui_synthetic.py`、`check_scenarios.py`、`check_close.py` 这些自己加载 QML 的
   脚本也都要跟着改（它们现在都吃 `OVERLAY_QML` 字符串）。
3. 收益主要是"文件变小"，风险是**界面错位/组件找不到**这类问题只在渲染时才暴露
   （只能靠 33 个渲染场景 + 56 项合成点击兜）；而这块界面现在是全绿的。

**结论**：拆不拆是"值不值得为可读性冒一次界面回归"的取舍，属于 owner 拍板的事。
真要拆，我建议分两步、每步都可回退：
① 先把 `theme` 变成 singleton（只改令牌，不改布局）→ 跑一遍场景；
② 再逐个搬组件（一次一个），每个都跑场景 + 合成点击。

### 28.3 验收

```
Ran 459 tests in 58.2s   OK（449 → 459）
覆盖率 91.4%（2619/2866）
clean_title 真实标题抽查：'坐牢成仙 - HTML5魔塔 和另外 14 个页面 - 工作 - Microsoft Edge' → '坐牢成仙'
skillinfo 真实数据：先攻 → 怪物首先攻击；纳魔为攻 → （空，按设计）
```

## 29. `__init__.py` 里不许写代码（2026-10-26）

owner 明确要求：**禁止在 init 里写代码**。当时仓库里有 9 个带内容的 `__init__.py`，
这一轮全部清空，内容搬到同目录的普通模块里。

### 29.1 搬去哪了

| 原来 | 现在 |
|---|---|
| `chaita/game/agent/__init__.py`（13 行，转发 Task/run + 四个子包） | 清空；调用方直接 import `agent.core` / `agent.monster.read` 等 |
| `chaita/game/agent/monster/__init__.py`（90 行） | `chaita/game/agent/monster/read.py` |
| `chaita/game/agent/map/__init__.py`（149 行） | `chaita/game/agent/map/read.py` |
| `chaita/game/agent/chat/__init__.py`（45 行） | `chaita/game/agent/chat/status.py` |
| `chaita/ui/__init__.py`（19 行，Qt 路径） | `chaita/ui/qt_env.py`（2026-10-28 之前叫 `qt_paths.py`） |
| `chaita/ui/controller/__init__.py`（5 行，只 import） | 清空；`startup` / `main` 直接 `from .controller.controller import Controller`（原 `base.py`，2026-10-28 拆成 jobs/window/session/controller 四个文件） |
| `chaita/ui/qml/__init__.py`（17 行，读 QML） | `chaita/ui/qml/loader.py`（原 `source.py`） |

**一个关键点**：搬文件时相对 import 的层数不用改 —— 相对 import 是按"包"算的
（`agent.map` 这个包在 `__init__.py` 还是 `read.py` 里，深度都一样），
所以模块内部一行都没动。

### 29.2 调用方怎么改的

- `chaita/game/read.py`：`from .agent import map as _map` → `from .agent.map import read as _map`
  （别名仍是 `_map`，所以 `_map.read(...)` / `_map.monsters(...)` 这些**调用一行没改**）。
  同理 `chat` / `monster`。
- `startup.py` / `overlay.py`：`Controller`、`OVERLAY_QML` 从新位置导入；
  两个文件顶部先 `from . import qt_env`（Qt 的 DLL/QML 路径必须在 PySide6 之前指好，
  以前这活在 `ui/__init__.py` 里）。
- 8 个自己 import PySide6 的模块（6 个 controller + 2 个 toolkit）都加了
  `from .. import qt_env`，这样单独 import 它们也不会找不到 Qt 插件。
- 工具脚本：`tools/_time_manual.py`、`compare_icons.py`、`compare_look_limits.py`、
  `compare_look_map.py`、`compare_map_stability.py`、`check_chat.py` 改成从新模块导入。

### 29.3 加了守门测试

`tests/test_layout.py`（2 条）：

- **仓库里所有 `__init__.py` 必须是空的**（一个非空就红，并列出是哪个、几行）；
- 三个功能的实现必须落在普通模块里（`monster/read.py`、`map/read.py`、`chat/status.py`）。

### 29.4 验收

```
仓库里 9 个 __init__.py：全部为空（test_layout 实测）
Ran 461 tests in 63.5s   OK（459 → 461）
界面自检 全部通过    真启动真关窗 退出码 0    crash.log 0 字节
tools/check_tools.py OK    check_deps.py OK    check_test_isolation.py OK    死代码 0
```

## 30. 顶栏三处改动 + AI 对话框不再收起（2026-10-26，owner 直接提的）

### 30.1 鼠标移到顶栏出现"巨丑的黑框"（已去掉）

`bar.color` 原来是：
```qml
color: mouse.pressed ? theme.surface3
     : (mouse.containsMouse && !overRead ? theme.surface2 : "transparent")
```
窗口是**圆角**、顶栏是**直角**矩形：悬停时铺上去的 `surface2` 在两个上角露出方角，
远看就是一个黑框。现在固定 `color: "transparent"`，悬停/拖动都不再变色（光标形状还在）。

### 30.2 顶栏那个折叠三角删掉

`▸ / ▾` 那个 `Text` 整块删除。分区标题（怪物/地图/技能/读取记录）的 `▾` 保留 ——
那是分区的展开标记，不是顶栏的。

### 30.3 顶栏点**任何地方**都能折叠/展开

原来只有"标题那一小块"能点（`pressX > buttonLeft - 6` 就 return，防误触）。
现在把这个判断删掉：顶栏空白处点了就折叠。按钮（读取 / ✕ / 折叠态那个 ↻）有自己的
`MouseArea`，按下会被它们吃掉、`engaged` 是 false，所以不会误触发。

### 30.4 "点折叠后顶栏布局变了"——真找到原因了

不是错觉。实测（510 宽、折叠态）：

```
旧：hero x=10  「拆塔辅助」x=156   ← 标题被推到中间
新：hero x=10  「拆塔辅助」x=44    ← 紧跟在图标后面
```

原因：那一行是 `RowLayout`，靠**塔名**（`towerLabel`）的 `Layout.fillWidth` 吸收多余空间。
塔名一为空（还没读过地图、标题栏没塔名）它就 `visible: false`，不再占位 ——
多出来的空间由 RowLayout 摊给别的孩子，把标题推到了中间。折叠/展开时 `towerLabel`
的文字长度在变，标题位置就跟着跳。

修法：加一个显式的"弹簧" `Item { Layout.fillWidth: true }` 放在塔名**前面**，
把塔名的 `Layout.fillWidth` 去掉。现在多余空间全被弹簧吃掉，左边这组
（图标 / 标题 / 读取）位置与塔名有没有、多长都无关。

### 30.5 AI 对话框不再收起

- 删掉提示行右边的「收起」按钮；
- 删掉"收起态"那一整条（`✎ 发现读错了？点这里直接说`，高 30px）；
- `chatBar.height` 固定 74，`chatExpanded` 这个属性整个删掉；
- 输入框里按 Esc 只把焦点还回去（原来会"收起纠错区"）；
  再按一次 Esc 还是退程序（`tools/check_close.py c` 实测：第一次 Esc 后窗口在、输入框在；
  第二次 Esc 0.02 秒退出）。

### 30.6 引导语挪进输入框的灰色占位文字

owner："发现读错了，这种东西放对话框的灰色文字里"。原来输入框上面单独一行提示
「发现读错了？直接说，例如「生命是1200」」，现在：

- 那句引导语变成输入框的 `placeholderText`（灰字："读错了就说，例如「生命是1200」"）；
- 上面那一行只在**模型回话了**的时候出现（绿色的回复），没有回复就整行隐藏；
- 聊天条仍是常驻展开（高度 74），没有「收起」。

### 30.7 地图行里的 ↻ 放大

字号 10 → 14，命中区余量 4 → 6（点得到范围约 19px → 26px）。
owner 那句"太小且…"后面还有半句没说完，等他补。

### 30.8 在对话框里打「你好」没反应（已修，两轮）

**第一轮我修错了。** owner："我在AI对话框输入你好怎么没反应？"。日志：

```
11:13:09  read.start  {"seq": 1, "active": 1}      ← 点了「读取」（怪物手册页）
11:13:58  read.done   {"seq": 1, "seconds": 43.3, "kind": "monsters"}
```

那 43 秒里 `_reading` 是 true，而 `sendChat` 第一行就是 `return`，一句话被静默吞掉。
我当时只是把静默改成提示（「正在读取画面，等这次读完再发。」），等于承认"对话必须排在读取后面"。

owner 随后一句话把方向掰正："AI对话框绑定你妈逼的读取"。对——**对话本来就不该依赖读取**。
读到什么只是对话的起点，没有起点也该能说。

**第二轮的做法：对话彻底独立。**

| 原来 | 现在 |
|---|---|
| 必须先点过「读取」（要有 `_last_status`） | 没有状态就传 `{}`，模型照截图给完整字段 |
| 必须知道是哪座塔（`_last_tower`） | 没有就用"最后一个前台窗口"现找（和读取同一套 `find_target`） |
| 读取期间发不出话 | 读取期间照样能发，不再共用 `_reading` |
| 找不到塔时说"先点读取" | 说"把游戏切到前台，再发一次" |

一句话 = 抓一次图 + 一次模型调用，和"读没读过"完全无关。改到的文件：
`chaita/ui/controller/chat.py`（重写，`_tower_for_chat` / `_chat_worker` / `_chat_done`）。

**真模型一测就露了第二个问题**：只回话的结果被判成失败。用存好的截图
`docs/capture/h5_miaomiao_212609.png`、状态传空 `{}`、不碰游戏窗口，连测：
「你好」第一次过了，第二次模型没给 `status`，`_parse` 就回
「模型没有给出修正后的状态」——用户看到的是"没改成功"。也就是说**"你好"能不能用，看运气**。

所以 `_parse` 改成两种回法都收：

| 模型给了什么 | 判成什么 |
|---|---|
| `{"status":{…},"reply":"…"}` | 改状态 + 一句话 |
| `{"reply":"…"}` | 纯回话，**不动记录**（`status` 为 None） |
| 什么都没有 | 才报「模型没有回话」 |

`_chat_worker` 里也跟着分岔：有 `status` 才写记录、才刷面板，没有就只把话显示出来。
prompt 也补了一句：玩家指正就改状态，只是打招呼就正常回话，别硬凑一个 status。

**顺手钉住了键名**：实测模型会自己发明 `"yellowKeys":0` 这种平铺键，界面只认嵌套的
`keys` / `special`，那样"黄钥匙是 2"会静默丢掉。prompt 里把字段表原样写进去之后：

```
'你好'                  2.0 s  status=None   reply「你好！我是拆塔记录助手，需要我根据截图更新状态时直接告诉我就行～」
'生命是1200，黄钥匙2把'  4.0 s  status.floor=1层 hp=1200 keys={"yellow":2,…}
'金币是350'             2.4 s  status.gold=350 special={…}
```

三句都没有 `_error`，键名都是界面认的那一套。

保留的两处**兜底**（都不是"读取依赖"，是防止界面冻住）：

- 上一句还在跑：「上一句还在处理，稍等一下。」——挡住并发，一句一句来；
- 60 秒没回音：自己收尾并说「这次等了 60 秒没回音…」。迟到的旧结果按序号丢掉，
  不会覆盖新的一句（`_chat_token`）。

界面状态一律回 UI 线程再改（`_post`），不在后台线程里碰 QML 属性。

测试：`tests/test_worker.py::ChatTest` 12 条（`test_chat_pure_reply_does_not_touch_status`
`test_chat_without_previous_read_still_works` 钉"没读过也能用"、
`test_chat_while_reading_is_allowed` 钉"读取期间也能发"）；
`tests/test_agent.py::ChatTest::test_reply_only_is_not_an_error` 钉"只回话不算失败"。

### 30.9 验收

```
tools/test_ui_synthetic.py   60 项全部通过（顶栏没三角 / 点两下折叠展开 /
                             没有「收起」入口 / 聊天条一直 74 高 / ↻ 字号 14）
tools/check_scenarios.py     33 个渲染场景全部干净
Ran 466 tests                OK
对话真模型实测               见 30.8（3 句，2.0~4.0 秒）
preview 出图：docs/capture/_ui_after_map.png / _ui_after_collapsed.png（都看过）
```

---

## 31. AI 对话框变成真的对话（2026-10-26，owner 直接提的）

owner："该功能不是单纯用于修改参数的！！它需要具有聊天功能！！"

之前那个框只做一件事：把玩家嘴里的一句话翻译成字段修正。模型被要求**必须**吐
`{"status":…,"reply":…}`，没有 status 就算失败。所以"你好"要么被当成改状态，
要么直接报错——它根本不是对话框，是个穿了输入框外衣的表单。

### 31.1 现在它是什么

| 之前 | 现在 |
|---|---|
| 只认"纠错"，prompt 里写死"你在帮玩家修正状态" | 聊天 / 问事 / 纠错都能说；`status` 是**可选附件** |
| 回话必须是一行 JSON，正文不许有别的 | 先正常说话，要改记录时**再另起一行**输出那行 JSON |
| 没有记忆：每句都是全新的 | 最近 8 轮随请求带上（`MAX_HISTORY`），"刚才那只怪"接得住 |
| 界面上只有最后一句绿色提示 | 面板多了「对话」一段，两边说过的话都在，能往下翻 |

模型侧：`chaita/game/agent/chat/reply.py`（`status.py` 已删）。
`_split_json()` 把"回话"和"JSON"分开 —— 裸 JSON、``` 围栏、JSON 里带 reply 三种都收。
回话为空才算失败。

界面侧：`MainWindow.qml` 里新增「对话」段（`objectName: "dialogLog"`），空记录时显示一句
"在下面的框里说话就行：问这层有什么、问刚读到什么，或者说「生命是1200」纠正它"，
有记录时一行一条，"你"用金色、"AI"用绿色。输入框占位文字跟着改成
「说句话：问点什么，或者「生命是1200」纠正它」。

python 侧：`controller/chat.py` 里 `_chat_log` 是**功能**不只是显示 ——
`sendChat` 把 `_chat_log` 传下去当上下文，所以在场的人都记得住。

### 31.2 真模型实测（三轮，`tools/check_chat.py`，只读存盘截图）

```
你：你好，先随便聊一句
AI（2.6 s）：你好。截图上是喵塔1层，生命300、攻15、防5，三色钥匙都是0把，
            跟我记的旧数据对不上——要不要我按截图更新？
你：生命不是 53，是 60
AI（2.9 s）：好，生命记成60，其他照旧。
    顺带改了：hp=60
你：我刚才让你把生命改成多少？
AI（1.7 s）：60，你说生命不是53、是60。
```

第一句是纯聊天、第二句改了记录、第三句考记忆 —— 三句都通了。

### 31.3 窗口没开也能聊

以前对话第一步就是"找游戏窗口"，找不到就只剩一句「把游戏切到前台」。可聊天不该被
窗口绑死 —— 游戏最小化时问一句"我还剩多少血"是合情合理的。

现在窗口/截图拿不到就 `image=None` 发下去，prompt 里多一句"这次没有截图"，
模型只能靠记录和上下文回答。真模型实测（无图，1.4 秒）：

```
你：现在没开游戏，你还记得我多少血吗？
AI：记得，1200 血，攻击 15，防御 5，黄钥匙 2 把。
```

### 31.4 顺手修的两个测试问题（不是产品改动）

1. **4 条测试靠着"真实前台恰好是游戏窗口"才过。** `_capture` 里用的是
   `capture.find_target / grab`，而这几条只打了 `game_read.grab_window` 的桩，
   所以前台不是游戏时它们就失败（实测：`find_window("msedge")=False` 时
   `read.error 前台不是游戏窗口`）。现在 `ReadOnlyTest` 和崩溃测试都补上了抓图层的桩。
2. 占位文字改了，`tools/test_ui_synthetic.py` 里按文字找输入框的两处跟着改。
3. **界面检查器漏掉了一整类文字。** 它按 `className() == "QQuickText"` 找文字，
   而带 id/property 的 delegate 会被 QML 编成 `QQuickText_QML_51` 这种子类名 ——
   整套对话流一条都找不到（第一版就是这么"测过了"。实测 `DEBUG kids=[…,
   'QQuickText_QML_51', 'QQuickText_QML_51']`）。现在按前缀判，并且排除
   `QQuickTextInput` / `QQuickTextEdit`。

### 31.5 验收

```
tests                        Ran 474 tests  OK
tools/test_ui_synthetic.py   70 项全部通过（含"对话不在上方的记录列表里"）
tools/check_scenarios.py     32 个渲染场景全部干净
tools/dead_code.py           定义未引用的函数 0 个
对话真模型实测                有图 3 句：2.6 s / 2.9 s / 1.7 s（见 31.2）；
                             无图 1 句：1.4 s（见 31.3）
```

---

## 32. 底部重新设计：对话坞 + 去掉三条横线（2026-10-26）

owner："说了设计UI，你要设计！！！！"、"丑爆了"。上一版把对话塞进上面那串记录里
（技能下面一段「对话」），结果是：记录一长对话就被挤出屏幕、跟你说话的地方隔着半个面板。

### 32.1 对话坞：气泡，长在输入框上

```
                    ┌─ 发丝线（左端淡出）+ 坞底色（比卡片亮 2.8%）
                    │    ┌──────────────────────┐
                    │    │ 这层还有几只怪？      │ ← 你说的：靠右、暖棕实色气泡
                    │    └──────────────────────┘
   ┌──────────────────────────┐
   │ 我记着 4 只：监狱守卫 ×6… │ ← 它说的：靠左、surface2 气泡 + 发丝边
   └──────────────────────────┘
                    [问点什么，或说「生命是1200」纠正它]  [↑]
```

第一版是裸文字（靠左右站位区分），owner 一句"毫无美感" —— 一列同字号灰字确实没有
对话的形状。现在是**气泡**：

| 项 | 值 | 为什么 |
|---|---|---|
| 你说的 | 靠右、`#3B3123` 暖棕实色、无边框 | 半透明金压在游戏画面上会发脏（试过 0.18/0.24 两档都发橄榄绿） |
| 它说的 | 靠左、`surface2` + 发丝边 | 和记录卡片同一档表面，但这个位置只有它在用 |
| 气泡形状 | 圆角 10、内边距 11/7、最宽 86% | 最宽留出对侧空气，两边都顶边就没呼吸了 |
| 对话流高度 | `min(内容, 200)`，再长里面滚 | 四条来回正好装下；再多就把记录区吃光 |
| 一条多高 | 行距 8、`lineHeight 1.3` | 12px 正文行距太挤，长句会粘成一块 |
| 坞底色 | `rgba(1,1,1,0.028)` + 卡片同圆角 | 滚到半截的气泡有个边可依，不像从记录里"漏"出来 |
| 没对话时 | 整块收掉（栏高 46） | 空槽位比矮一点更难看 |
| 新消息 | 淡入 + 从下托 6px（160ms OutCubic） | 直接"啪"出现最显廉价 |
| 等回话 | 三个点错峰呼吸 | 比"正在回你"的横幅安静 |
| 出错 | 红字气泡（`tone: "danger"`） | 错误也是对话的一部分 |

### 32.2 过渡（owner："连过渡都做不好"）

上一版有**三处会跳**，都改了：

1. **栏高跳**：`Behavior on height` 是有的，但高度一变，比栏还高的子项会盖到上面的
   记录上 —— 加了 `clip: true`。
2. **内容跟着上沿跳**：`ColumnLayout` 原来锚**顶边**，栏往上长的过程中整块内容跟着
   上沿一起跳，输入框会飞。改成锚**底边**，长高时输入框贴着窗口底不动，上面的对话
   被"露出来"。
3. **悬停硬切**：输入框聚焦描边、发送键悬停底色改成 120ms `ColorAnimation`。

实测（`tools/preview_overlay.py … dock-grow`，每 40~60ms 取一次 `chatBar.height`）：

```
t10  71.2
t50 115.2
t110 145.8
t200 153.0     ← 到这儿停住
```

是渐变，不是跳变。另外 `tools/test_ui_synthetic.py` 每 20ms 取一次输入框在屏幕上的
y：全程 `y 674~674`，一格都没动。

### 32.3 输入行：一个盒子 + 一颗 ↑

- 输入框 26 → 30 高、字号 12 → 13、内边距 10，聚焦时描边转 brand（120ms）；
- 「发送」56×26 的黄块 → 30×30 的 ↑ 方键（`surface2` + 1px 边，悬停才转 brand）——
  底部不要再出现第二块大黄跟顶部「读取」抢；回车本来就能发，按钮是辅助；
- 占位文字改成「问点什么，或说「生命是1200」纠正它」（原来那句话太长，被截断）；
- 发丝线左端 18% 处淡入，不再从边到边一刀切死。

### 32.4 右下角那条横线删了、面板底部不再一刀切

- 三条横线只是装饰 —— 真正能拖的是 Windows 命中测试（`toolkit/desktop.py` 的
  `_BORDER` 边），删掉不影响缩放，靠"移到边上光标变斜箭头"提示。
- 内容区底部加 18px 渐隐（`14,16,19` 从透明到 0.94），被聊天条挡住的那半行变成淡出。

### 32.5 空面板：几百像素的空白（owner 截图里那一大块）

owner 发的截图：四个 `0` 的标题下面是一大片空白，看着像界面没加载完。

原因：那一句引导原来只在**没有**「上次的记录还在」提示时才显示
（`visible: win.isEmpty() && controller.sessionHint === ""`）。于是"有旧记录但还没点恢复"
这个状态下面板一句话都没有。

现在是一页**居中的空白页**：

```
                 还没读过东西
        切到游戏窗口，点上面的「读取」
      手册页读怪、地图页读这一页，它自己认。
        上次的记录还留着，点「恢复」也能接着用。
```

另外"矮窗口"也修了：对话坞最多占窗口高度的 30%（而且总高不超过 `窗口高 - 160`），
420 高的小窗里不会再被聊天吃光。

### 32.6 验收

```
tests                        Ran 474 tests  OK
tools/test_ui_synthetic.py   72 项全部通过（新增：没对话时聊天条 46 / 对话流长出来了 /
                             栏高到位 / 过渡时输入框没跟着跳 / 你那句在 / 它那句在 /
                             对话不在上方记录列表里 / 你说的话单独一类）
tools/check_scenarios.py     32 个渲染场景全部干净
栏高过渡实测                  71 → 115 → 146 → 153（见 32.2）
preview 出图（都看过）：docs/capture/_ui_dock_chat.png（气泡版对话坞）
                        docs/capture/_ui_dock_long.png（长到上限后滚到最新）
                        docs/capture/_ui_dock_grow_mid.png（长到一半的样子）
                        docs/capture/_ui_dock_empty.png（没对话时只有一个输入框）
                        docs/capture/_ui_empty_hint.png（空面板：居中那句引导）
                        docs/capture/_ui_his_size.png（439×868，owner 那个窗口尺寸）
```

> 注：验证时发现**你正开着一个旧版本的窗口**（pythonw，11:11 启动，占着单实例锁），
> 所以 `smoke_close.py` 被"已经开着了"挡了回来 —— 这也说明单实例保护是生效的。
> 想看到上面这些改动，得先把那个窗口关掉再重新打开。

---

## 33. 小窗八面能拉、怪/资源的图不再空、行距收紧（2026-10-27 晚，owner 一次三条）

owner 原话："地图界面怪物和资源的行间距太大了"、"怪物和资源的缩略图怎么没有了"、
"怎么只有右下角能拉伸窗口"。

### 33.1 行距：行高 30 → 24

`floorMonRow` / `floorItemRow` 都是 30 高，里面只有 20 的缩略图和 10 号字 —— 上下
各空 5px，看着像"每条之间空一行"。现在行高 24（图 20 + 上下各 2），怪物区和资源区
之间的空档 14 → 10。字段框仍是 22 高，没被压。

### 33.2 缩略图为什么是空的（三个原因叠在一起）

1. **资源**：`itemIcon(name)` 无脑拼 `itemBase + name + ".png"`。而 AI 读画面裁下来的
   资源图是一串 `file:///...Temp/chaita/....png`，被当名字又拼了一遍 —— 变成
   `file:///<items>/file:///...`，必然打不开。现在 URL / 绝对路径原样返回。
2. **空框**：`visible: win.hasUrl(icon)` 只管"有没有字符串"。文件被清掉以后
   `hasUrl` 仍然是真，于是画一个打不开的 `<Image>` —— 既没有图，也不退回首字，
   就是一个洞。三处（主窗口怪列表、地图怪行、资源行）都改成
   `visible: status === Image.Ready`，怪行退回首字、资源行干脆不占位。
3. **地图行的怪只认手册**：`monsterIconNamed()` 只在 `controller.monsters`（这次读
   手册读到的）里按名字找。没读过手册的怪就只剩首字。现在多一层兜底：
   `controller.libraryIconByName()` 去素材库按名字找（显示名 / 两座塔里的原名 /
   并掉的别名，**只认完全同名**，不模糊匹配）。

   ⚠️ 数据边界：拆个魔塔的怪（血蚊 / 铁卫 / 监狱守卫 / 上级魔法师）**不在素材库里**
   （素材库是两座新新魔塔的图），所以这些怪没读过手册时还是只有首字。要真给它们
   配图，得在"读地图"时顺手把格子里的怪也裁下来 —— 那是新功能，等 owner 点头。

顺带：`_get_map_history()` 会把指向已经不存在的 Temp 文件的 `icon` 清掉
（`floors._dead_icon_file`），别把死链一路存下去。

### 33.3 小窗只有右下角能拉 → 八面都能拉

先试的"正道"：把「这一层」也交给 Windows 的 `WM_NCHITTEST`（`NativeHitTest` 认
多窗口 + 加 `WM_ENTERSIZEMOVE/EXITSIZEMOVE` 标记），探针实测**失败**：这扇窗的
`width/height` 是 QML 绑定出来的，系统改尺寸以后绑定按旧值把窗口顶回去，一通乱拖
之后窗口被顶成 `13×280`（日志见 `logs/_probe_sheet_resize.txt`）。撤回。

改成 QML 自己的把手：一个 `SheetGrip` 组件（四边布尔 + 可选斜线标记）摆 8 处，
`floorGrip`（右下，保留三道斜线）/ `floorGripL/R/T/B` / `floorGripTL/TR/BL`。
两条容易踩的：
- 位移必须用**屏幕坐标**（`mapToGlobal`）：窗口自己在动，用窗口内坐标算出来的位移
  会越拖越小（实测拖 22px 只挪 11px，和拖抬头那条同一个坑）；
- 每帧把新尺寸记进 `floorSizes`：这扇窗的宽高是绑定出来的，不记就顶回去。

探针 `logs/_probe_sheet_grips.py`：8 个方位逐个真拖 40px，结果全部与预期一致
（左边 x-40/w+40、上边 y-40/h+40、四角两个方向都对）。

### 33.4 验收

```
tests                        Ran 681 tests  OK（新增：八面拉 / libraryIconByName / 死链图标）
tools/test_ui_synthetic.py   ==== 结果：全部通过 ====
tools/check_scenarios.py     floor / flooritems / floorsmall / floorpick 全部 OK、warnings=0
真拖探针                      logs/_probe_sheet_grips.txt（8 个方位全对）
出图（都看过）                logs/_floor2.png（行高 24）
```

---

## 34. 模型自己起的名字会污染「怪物」栏（2026-10-27 深夜）

owner 原话："我读取怪物后再刷新第0层怪物手册里出现了垃圾词条还覆盖了我的正确怪物词条"。

### 34.1 复现（用的是 owner 真实的 `logs/last_session.json`）

```
手册：绿色史莱姆、红色史莱姆
0层 ：红史莱姆 ×2、绿史莱姆 ×3      ← 早期读地图时手册还空着，模型自己起的简称
```

`monster_names.match_one("红史莱姆", ["绿色史莱姆","红色史莱姆"])` → **""**：

- "红史莱姆" 和 红色史莱姆 / 绿色史莱姆 的**最长公共子串都是"史莱姆"（3）**，
  分数一样 → 按"一样像就当没对上"的规则返回空；
- 于是 ↻ 的结果是：旧行一个没改（`renamed_old: 0`），这次读到的 2 只全被丢掉
  （`dropped: 2`、`found: 0`）—— 数量再也不更新；
- 而「怪物」栏会把"手册里没有的地图怪"另起一行（`monsterRows()` 里的 extras），
  所以列表里同时出现 红色史莱姆（×0）和 红史莱姆（×2）。

复现脚本：`logs/_probe_garbage_names.py`，输出 `logs/_probe_garbage.txt`。

### 34.2 修法（三处，都是"把名字对到手册写法上"）

1. `monster_names.match_one()`：同名之后先判**唯一子序列** —— "红史莱姆"的字按顺序
   都出现在"红色史莱姆"里，而绿色史莱姆里没有"红"，所以唯一命中；"史莱姆"能装进
   两只 → 仍然判"对不上"（宁可漏，不许记错）。落到最长公共子串只是最后的兜底。
2. `reading._align_floor_rows()`：手册读到名字以后，把地图上那些模型起的名字**就地
   改名**（数量、打过的勾、换过的图标、手改的效果都不动；两行对成同一只的并一行、
   数量取大的）。三个调用点：读手册之后、恢复上次记录之后。
3. `_deliver_monsters()`：同一页读两次、第二次名字读短了，先归一再加 —— 不许在
   手册里多出一行（用户："垃圾词条"）。归一后同名的仍然**不覆盖**老记录。

顺带把「↻ 找不到这一层」从静默 `return` 改成任务队列里写明失败（以前点了像没反应）。

### 34.3 验收

```
tests（新增 3 个用例文件/类）  test_monster_names（8 条：简称/歧义/标点/错一个字）
                              test_scan_merge +3（早期简称被 ↻ 改正 / 读手册就改 /
                                读两次不多行）
                              test_overlay +1（恢复上次记录时改掉模型起的名字）
全量                          Ran 694 tests  OK
探针                          logs/_probe_garbage2.txt：刷新后 [('红色史莱姆', 2), ('绿色史莱姆', 3)]
```

⚠️ owner 现在开着的那个实例里还是脏数据：**关掉重开、点「恢复上次记录」**就会自动
改正（存档里的 `红史莱姆` 会被改成 `红色史莱姆`，数量不变）。

---

## 35. 造景数据必须"实际会出现"（owner 点名）

owner 原话："你测试用的地图都带人物信息，实际根本不可能"、"用fixture没问题，但你的
fixture不是实际会出现的"。

### 35.1 病根

1. **图是整窗截图**：`tools/preview_overlay.py`、`tests/test_integration.py::_thumb_url()`、
   `tools/test_ui_synthetic.py::_save_thumb()` 都把整张窗口截图当地图缩略图 ——
   带着浏览器标签栏和左边的生命/攻击/钥匙面板。真实「读地图」落到磁盘的只有
   `read.map_snapshot()` 裁出来的方图。
2. **数据是编的，而且互相矛盾**：塔名「坐牢成仙 地下30」+ 地图其实是另一座塔的
   通天塔1；怪「血蚊 1200 / 监狱守卫 21000万」；**两张同一个截图**分别当 地下30 / 地下29；
   生命 1200 金币 9800。任何一局都不会长这样。

### 35.2 改法

- 三处都先 `read.map_snapshot(tower, image)` 裁成真地图再存：
  `preview_overlay._map_shot()` / `test_integration._thumb_url()` /
  `test_ui_synthetic._save_thumb()`。
- 造景换成 `docs/capture` 里**录下的那一局**（拆个魔塔 · 通天塔1）：

  | 造景里的 | 真值来源 |
  |---|---|
  | 塔名 / 层 / 生命 53 | 日志 `read.status {"name":"拆个魔塔","floor":"通天塔1","hp":53}` |
  | 地图截图 | `_repro2.png` 按塔裁出来的方图 |
  | 5 只怪的 生命/攻击/防御/经验 | `_manual_repro.png` 手册页：红头怪 80/25/1、骷髅人 200/50/10、小蝙蝠 100/30/3、青头怪 100/26/3、大蝙蝠 120/35/5 |
  | 攻击 3 / 防御 2 / 金币 4 / 黄钥匙 1 | `_repro2.png` 左侧面板上印的数 |

  只留**一层**（以前拿同一张图当两层）。技能（破甲 / 吸血 / 领域）挂在骷髅人和青头怪
  身上，是"用户自己从下拉里加的"——app 允许，属于会出现的状态。
- `preview_overlay._sprite()` / `_SPRITES` 删了：不再把**另一座塔**的素材图塞进造景。
- `check_scenarios` 期望高度跟着改：`folded` 466 → 438（造景只有一层地图）。

**仍然是我编的、但量级合理**：这一层各几只（4/1/3/2/1）、资源几个、以及伤害计算场景里
的人物数值（50000/120 —— 不然通天塔1 的怪一个都打不过，图看不出效果）。图上没有可信
来源的地方只能给"这层会出现"的量级，别再出现 21000万 那种。

### 35.3 验收

```
check_scenarios   26 个场景全部 OK（默认 986；floor/flooritems/floorpick 1017；folded 657）
出图（都看过）      logs/_default4.png（拆个魔塔 通天塔1：5 只真数值、一层真地图）
                  logs/_floor3.png（小窗里是裁好的方图，没有人物面板/浏览器）
```

---

## 36. 资源行的缩略图 / 效果只改数值 / 点已开的小窗要前置（2026-10-27 深夜，owner 三条）

### 36.1 资源的缩略图（"地图界面的资源的缩略图呢？"）

图标来源本来就两条：`iteminfo.icon_for(名字)`（红宝石 → `gem_red`）和存档里留的
`icon`（可能是 AI 裁的临时图 URL）。两条都能拿到图，问题是**打不开的时候留了个洞**：
`Image` 只按"有没有字符串"判可见，文件没了就一片空白，连首字都没有。

现在：
- `itemIcon()` 认三种写法（素材名 / `file://` URL / 绝对路径），不再把 URL 拼到
  `assets/items/` 前面（那是"必然打不开"的老 bug）；
- 打不开就给**首字占位**（`floorItemIconFallback`），和怪物行一个规矩；
- `_get_map_history()` 把指向已删除临时图的 `icon` 清掉（`_dead_icon_file`）。

### 36.2 宝石的属性写死、数值能改

用户："宝石加的属性要写死，加的数值要能改"。

- `iteminfo.split_effect("攻击力 +2")` → `("攻击力", "+2")`；
  `join_effect("攻击力", "5")` → `"攻击力 +5"`（符号认 `+` / `-`）。
- 界面上效果那一格拆成 **`floorItemEffectLabel`（Text，只读，道具表定的属性）** +
  **`textInput` 显示数值（`floorItemEffect`，改了调 `saveItemEffectValue`）**；
  没有数值的效果（"可以打开一扇黄门"）整段只读，不给输入框。
- 存回去还是 `"属性 +N"` 一个字符串（存档不用改结构），并置 `effect_manual`
  —— 显示层不会再用道具表把它盖回去。

### 36.3 点已开的地图块 → 把那一扇窗提到最前

用户："我不关闭小窗再点地图没反应，应该把对应窗口前置"。

`openFloorSheet()` 以前只是把名字挪到 `floorWindows` 末尾，窗口不会浮上来。
现在如果这一层已经开着，还会 `show() + raise() + requestActivate()`。

### 36.4 验收

```
tests（新增 6 条）   iteminfo.split/join 3 条、控制器 saveItemEffectValue 2 条、
                    界面「属性只读 + 数值可改」、点已开的小窗只保留一扇且排到最后
全量                Ran 701 tests  OK
tools/test_ui_synthetic.py   ==== 结果：全部通过 ====
check_scenarios      floor / flooritems / floorsmall / floorpick 全 OK、warnings=0
出图（都看过）        logs/_flooritems6.png（黄钥匙只读、血瓶/宝石只有数值可改）
```

---

## 37. 资源按 owner 定的顺序排（2026-10-27 深夜）

owner 原话："地图界面的资源要按宝石（红蓝绿黄）武器防具血瓶钥匙排序"。

以前是"钥匙 → 血药 → 宝石 → 武器 → 防具 → 其他"（早期"按魔塔里的习惯"我猜的），
现在按 owner 点名的顺序：

```
宝石（红 → 蓝 → 绿 → 黄）→ 武器 → 防具 → 血瓶 → 钥匙 → 其他
```

- `iteminfo.KIND_LABELS` / `_KIND_WORDS` 的下标整体换了；`kind_rank` 里
  "认不出但标了 equips" 的兜底也跟着指到武器（1）。
- 颜色次序分两张表：`_GEM_COLOUR`（宝石：红蓝绿黄…）和 `_COLOR_RANK`
  （其它类沿用黄蓝红绿铁魔）。`sort_key` 先用 `kind_rank` 选表再取颜色。
- `choices()`、`sortedSheetItems()` 都走 `sort_key`，一处规则。

验收：

```
回归    tests/test_iteminfo.py 重写两条（新顺序 + 宝石四色）；
        tests/test_integration.py 三处跟着改：资源行顺序断言换成
        ["红宝石","铁盾","红血瓶","黄钥匙"]；`test_add_save_remove` 不再假定新加的
        排在第 1 行（宝石现在排最前）；资源换种类的用例改成点**第一行**（钥匙现在排
        最后，菜单一打开看不到它，点不到）
全量    Ran 702 tests  OK
自检    tools/test_ui_synthetic.py ==== 结果：全部通过 ====
出图    logs/_flooritems8.png（红宝石 → 红血瓶 → 黄钥匙）
```

---

## 38. 伤害计算的「加一步」菜单：两个标签页（2026-10-27 深夜）

owner 原话："害计算器点问号后添加的界面里面没用的东西太多了，应该只有两个标签页
分别是怪物和资源包含（4色宝石）"。

以前是**一个长列表**：手册里的怪 + `iteminfo.choices()` 的 76 条资源全摆在一起，
其中一大半是书/证明/锄头这种跟掉血无关的东西。

现在：

- 菜单顶上加两个标签页（`battleTabMonster` / `battleTabItem`，选中戴胶囊底），
  默认「怪物」；切换走 `battleSwitchTab()` → `battleRefreshPick()`。
- 资源那页只留**算得出加成**的：`battleItems()` 用 `battle.parse_item_effect()`
  过滤 —— 和真正计算用的是同一个解析器，不会出现"列表里有、加进去却没效果"。
  76 条 → 23 条。
- **四色宝石无条件保留**（`iteminfo.GEM_STEMS` / `is_gem()`）：绿宝石加的是敏捷、
  算式里没有敏捷这一项，按"算不出加成"会被滤掉，但它是玩家一定要拿来算的东西 ——
  用户点名"资源（包含 4 色宝石）"。
- 空页给一句话（"手册里还没有怪，先读一次怪物手册" / "没有能算加成的资源"）。
- 菜单卡高度 / 摆放估算跟着加高的标签行（30 → 56），翻转判断一起改。

验收：

```
tests    新增 2 条：菜单只有两个标签页 + 默认页是怪 + 资源页含 4 色宝石、不含书/证明；
         `battleItems()` 只留能算出加成的
全量     Ran 704 tests  OK
场景     battle / battleplan / battlecmp / battleinsert / battlepick / battleedit 全 OK
出图     logs/_battle_menu.png（怪物页）、logs/_battle_itemtab.png（资源页，四色宝石在最前）
```

新增预览场景 `battlepick`（问号菜单停在「资源」页）—— `check_scenarios` 里也登记了。

---

## 39. 读两只只记一只（2026-10-27 深夜，owner：名字被"最像的"并掉了）

owner 原话："怎么读怪物不全？" → "读取记录显示读取两只但看怪物只有一只"。

### 39.1 病根

§34 为了让"同一页读两次、第二次名字读短"不多出一行，我在 `_deliver_monsters()`
里先拿 `monster_names.match_one()` 归一再决定要不要加。那个函数最后有一步
**"取最像的那个"**（按最长公共子串），本意是给**地图上按图案猜名字**用的。结果：

```
读手册读到 小蝙蝠  →  和已有的 大蝙蝠 共"蝙蝠"两个字
                   →  match_one 返回 大蝙蝠
                   →  "已经记过了"→ 丢掉
```

于是"手册 2 只"、列表里 1 只。花名册上少一整只怪。

### 39.2 修法

`match_one(name, known, strict=False)` 加严格模式，读手册时用：

- 一模一样 → 用；
- **只认"中间少了个修饰字"的缩写**（子序列 + 首字相同 + 尾字相同）：
  「红史莱姆」⊂「红色史莱姆」→ 同一只（这是 §34 要保的那条）；
- 「小蝙蝠 / 大蝙蝠」（首字不同）、「血蚊 / 血蚊王」（尾巴变长）→ **两只不同的怪**，
  绝不合并。

地图上按图案猜名字那一路（`align()` / `_apply_scan`）仍然用松散模式
（「青头怪」→「绿头怪」那种），那条是给"图上没字"用的，不能一刀切。

另外记录行现在写清楚：
`手册 2 只（新增 1，1 只已记过）`，不再只报"读了几只"，免得看着像丢数据。

### 39.3 为什么老用例没拦住（owner 追问："这个问题之前的 integration test 没测出来吗？"）

没测出来，三个原因叠在一起：

1. **唯一"读两只"的用例用的是「甲/乙」**（`test_editor.test_manual_reread_reports_new_count`）。
   这类名字在"最像的那个"那一步永远返回空（没有任何两个字相同）→ 两只都新增 →
   用例绿。**用例的形状对，数据对不了**。
2. §34 我新加的两条只测了"**该并**的那一侧"（红史莱姆 → 红色史莱姆），
   没测"**不该并**的那一侧"（小蝙蝠 / 大蝙蝠）—— 覆盖了我正在加的行为，
   没覆盖同一个函数里同时存在的风险。
3. 用真名的手册用例都只有**一只**（红头怪、骷髅人），从来没有"同一页上的最小对立对"。
   真实的通天塔1 手册页上恰好就有「小蝙蝠 / 大蝙蝠」。

实测对照（`logs/_why_missed.txt`）：

```
旧规则(松散) 小蝙蝠 vs 大蝙蝠   -> '大蝙蝠'    ← 会被当成已记过、丢掉
旧规则(松散) 乙     vs 甲       -> ''          ← 照常新增（用例就这么过的）
```

补的用例（这次用真数据，不再用甲/乙）：
- `test_no_two_real_names_on_one_page_are_merged`：把那一页的 5 个真名**两两跑一遍**，
  任何两只不同的怪都不许被判成同一只；
- `test_a_real_manual_page_records_all_five_monsters`：整页读一次，5 只全在；
- 另外两条：严格模式的正反例、记录行写"新增 N / M 只已记过"。

### 39.4 验收

```
tests    新增 5 条（含 2 条用真名的最小对立对/整页读取）
全量     Ran 710 tests  OK
```

## 40. 伤害计算窗口的 7 条（2026-10-28 凌晨，owner 一次点名）

owner 原话："伤害计算界面怎么不能拉伸窗口，怪物和资源得缩略图太大了，箭头太丑了，
而且不明显，伤害外面要加括号，我加的怪和资源一多就该换行，计算按钮要在每一条对吼
（后面），血攻防魔防怎么不像状态一样显示"。只动这一扇窗，别处一行没碰。

### 40.1 改了什么

| 点名 | 改法 |
|---|---|
| 不能拉伸 | `BattleGrip`（`SheetGrip` 同一套算法）摆 8 处；尺寸记进 `win.battleWinW/H`，宽高从"绑定内容"改成"用户拉过就用用户的" |
| 缩略图太大 | `battleSlotW` 20 → 14，行高 30 → 26 |
| 箭头丑/不明显 | 9 号 `→` 字换成 `ChainArrow`：两条 1.6px 短线拼 `>`（`battleArrowLeg`）+ 药丸底 + 琥珀 hover，点区 14×26 |
| 伤害加括号 | `（−930）` / `（打不了）` |
| 一多就换行 | 链从 `Flickable + Row`（左右滑）换成 `Flow`，行高 `max(26, flow+2)`，窗口高度跟着长 |
| 计算在每一条后面 | `battlePlanRun` 从右边那列搬到链尾（问号后面）；右边那列只留"总掉血/剩血" |
| 血攻防魔防像状态 | 去掉四个带标题的输入框，改成 `iconBase` 的 hp/atk/def/mdef 图标 + 44 宽的数，聚焦才有浅底琥珀框 |

顺带必须跟着改的两处（属于同一件事，不是顺手动别的）：

- `placeMenu()` 以前用"第几行 × 行高"算菜单位置，**折行以后就错了**；改成把那一行的
  坐标 `mapToItem` 过来（`battleRowItem(planIndex)`），并且 `battleFlick.onContentYChanged`
  时重算 —— 滚动以后菜单要跟着那一行走。
- 抬头/人物/按钮三行从写死的 `y: 34 / 72 / 106` 改成 `anchors`，滚动区高度用
  `battleCard.height - chainTop - chainBottom`，拉大拉小都自洽。

### 40.2 怎么验的

- `tests/test_integration.py`：新增 7 条（窗口四边八角 + 真拖拽改宽高、缩略图 14、
  箭头是两条斜线、括号、10 格折行且问号掉到下一行、`battlePlanRun` 在链尾同一行、
  四个人物数前面有图标）；老的掉血断言改成 `（−900）`。
- `tools/test_ui_synthetic.py`：加 5 条 `check`（四边八角在、缩略图 14、箭头两条斜线、
  `battlePlanRun` 和问号同一个父节点、人物数宽 <= 60），掉血检查改成括号。
- 截图：`logs/_scenarios/battle*.png`（`check_scenarios` 6 个场景 0 warning），
  另外把窗口缩到 320×240 手看过折行/不重叠（`logs/_battle_resized.png`）。

### 40.3 验收

```
tests     Ran 718 tests  OK（新增 7 条）
synthetic 全部通过（battle 段 5 条新 check 全 PASS）
scenarios battle/battleplan/battlecmp/battleinsert/battlepick/battleedit  全部干净
```

## 41. 「＋ 加资源」只列 owner 指定过的（2026-10-28 凌晨）

owner 原话："这地图下得加资源都是什么乱七八糟的，我应该明确指定过有哪些吧"。

### 41.1 病根

`iteminfo.choices()` 当时拼了三块：`item_effects.json`（8 件）+ `items/map.json`
（owner 指定的名字→图标）+ **`item_catalog.json` 整表（99 件）**。最后那块是
"新新魔塔1 + 新新魔塔2"两座**别的塔**的道具（宝石锄头 / 宝石剑 / 深红(Z3) / 圣锤 /
随意门……），和正在打的「拆个魔塔」没关系。下拉实测 **76 条**，前 4 条宝石之后全是
那些东西（改完是 7 条，见 `logs/_additem_new.png`）。

这块是当初为"资源里资源种类不全怎么没有武器和防具还有钥匙"加的 —— 那条要求被
实现成了"把两座塔的道具表全倒进下拉"，从"太少"直接翻到"太多"。

### 41.2 改法（owner 选的是"只列我指定过的"）

- `iteminfo.choices()` **只读 `assets/items/map.json`**（owner 指定的"资源名→图标"），
  按图标去重 + 血瓶合并成一条 → 7 条：
  红宝石 / 蓝宝石 / 绿宝石 / 黄宝石 / 铁盾 / 血瓶 / 黄钥匙（顺序仍按 §宝石→防具→血瓶→钥匙）。
- `item_effects.json` / `item_catalog.json` 降级成**查表**（`effect_for` / `icon_for`）：
  下拉里那 7 条的效果还是从这两张表带出来的（红宝石=攻击力 +2、黄钥匙=可以打开一扇黄门…）。
- `Controller.itemChoices()` 里那段"表没建就退回 map.json"的分支删了（现在 choices()
  本身就是 map.json，留着是两份实现同一条规则）。
- 同一份列表还喂着"点资源图标换种类"（`setItemKind`）：那边也一起变成这 7 条了。
  想加新种类只有一条路——往 `assets/items/map.json` 里加一条名字+图标。

### 41.3 测试

- 新增 `test_choices_are_only_what_the_owner_specified`（就是那 7 条，顺序也钉住）、
  `test_tower_catalogs_never_leak_into_the_dropdown`（宝石锄头/圣锤/深红(Z3)/铁剑…
  一条都不许进，条数 < 20）。
- 删掉 `test_catalog_has_keys_weapons_armor`（它钉的是已经被推翻的旧要求），
  `test_item_effects_come_from_game_data` 的后半截（"允许十几条没说明"）改成
  "下拉里每一行都必须带效果"。
- 截图：`logs/_additem_new.png`（7 条，带效果）。
- 顺手修了全量跑时偶发的一条红（不是这轮改出来的，是测试自己的排序假设）：
  `tests/test_integration.py::find_all` 的 walk 用栈弹出来的顺序是**反的**（第 2 行
  排在前面），平时靠 scene y 排序盖住；Repeater 刚重建、还没排版的那一帧 y 全是 0，
  顺序就露出来 → `test_deleting_a_row_and_clearing` 点"第 1 行的 ✕"删掉了第 2 行。
  现在 walk 按**声明顺序**（子节点倒着压栈），位置打平时保持声明顺序。

### 41.4 验收

```
tests      Ran 719 tests  OK（连跑两遍都绿）
synthetic  全部通过
scenarios  floorsmall 0 warning
```

## 42. 刷新读进来的资源没有图标（2026-10-28 上午）

owner 原话："地图我点刷新，怎么读进来的资源还是没有图标？"

### 42.1 复现

走真路径（`_apply_scan`，"刷新本层"就是它）：AI 只给名字和数量 →
`{"name": "红血瓶", "count": 3, "icon": "", "effect": ""}`。然后看两处：

```
库里存的              icon='' effect=''
主界面 _get_map_history  icon='potion_red' effect='体力 +150'   ← 显示层补了
「这一层」sortedSheetItems icon='' effect=''                   ← 没补 ← 用户看到的
```

`_get_map_history()` 里那段"名字→图标、道具表→效果"只服务主界面的地图块；
点开「这一层」清单走的是 `sortedSheetItems()`，它直接 `dict(item)`，空白一路
透到界面 —— 于是清单里全是占位框。

### 42.2 改法

把那条规则收成**一份实现**：`Controller._fill_item_display(item)`
（图标：名字→道具表优先，查不到才用行里存的；临时图不在盘上的丢掉；
效果：表里有就以表为准，`effect_manual` 不动），然后四个地方都走它：

| 地方 | 作用 |
|---|---|
| `_get_map_history()` | 主界面地图块（原来那段内联逻辑搬进 helper） |
| `sortedSheetItems()` | **「这一层」清单（用户看到的就是这里）** |
| `_apply_scan()` | 刷新落库时就把新行填完整（老行也顺手补） |
| `_attach_items()` | 读地图落库时同样填完整（原来只补效果，还留着一份重复逻辑） |

这样存进去的记录自己就是完整的（session 存下来也对），不靠界面兜底。

### 42.3 测试

`tests/test_editor.py::RefreshItemIconTest`（5 条）：
刷新后清单里有图有说明、**存的那一行**也完整、老记录（icon 空的）显示时补上、
道具表里没有的（神秘道具）不硬凑图、`effect_manual` 不许被盖回去。

截图 `logs/_sheet_icons.png`：清单里红宝石/红血瓶/黄钥匙都有图，"神秘道具"是
占位框 + 「神」。

### 42.4 验收

```
tests      Ran 724 tests  OK
截图       logs/_sheet_icons.png
```
