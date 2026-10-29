# 素材命名工作流程（`assets/library/monster/`）

这份文件写"怎么一张一张看图、给素材命名、处理重复"，以及**用户已经定过的规矩**。
每次动手前先读它；用户给新规矩时**立刻补进这份文件**（用户："工作流为什么不改"）。

## 0. 铁律

1. **一次只看一张图**，按文件名编号顺序（001、002、003…），看完立刻回报：
   图里是什么 + 名字判定 + 是不是重复。不许攒批、不许跳号。
2. **有问题就停，等用户决定**（用户："听懂没有有问题就停，等我决定"、"有问题就停！！！非要我手动吗？"）。
   重复、名字与图不符、种族归错、带底纹、同名两个文件——都算"有问题"：**停下问，不许自己往下推**。
3. **禁止自创名字**（用户："你禁止起名"）：
   - 先用**游戏内名字**（那座塔 `project/enemys.js` 的 `name`）；
   - 游戏里没有这个概念（比如"种族"）时，**问用户要名字**；
   - 不许自己造词（"蛮族 / barbarian" 就是这么被否掉的）。
4. **重复怎么算**：
   - "重复"只指**同一张画的两份**：像素几乎一样（容差后 ≤2% 可见差异），或一张带底纹一张干净。
     → 留干净那张、删另一张；被删的 id 记进 `alias_ids`（存档里的 `icon_id` 仍能查到图）。
   - **换色重绘不是重复**（用户："18，19是不同的怪"：骷髅兵 / 中级骷髅兵）。
   - **同名但不同画可以并存**（用户对两个「丧尸士兵」说"保持现状"）。
   - **不重复就不删**（用户原话）：只有确认是同一张画的两份才删；
     拿不准就停着问，**不许因为"看着像"就删**。
5. **编号规则**：`编号_种族_英文名.png`，编号 = 显示顺序（同类相连、弱的在前），
   全 ASCII，不许中文、不许拼音。
6. **英文要有英文习惯**（用户："你这个命名符合英文习惯吗"）：
   - 修饰词在前、名词在后：`robed_mage`（不是 `robe_mage`）；`slime_man`、`demon_king` 同理；
   - 名字那一截**不重复种族词**：`robed_mage_blue`，不是 `robe_mage_robe_mage_blue`；
   - 用户认可过的级别词照用：`mid`（中级）、`high`（高级/上级）；不要再自造（`adept`/`veteran` 已被否）。
7. **归类顺序**：游戏名 → 名字里的词 → 贴图键；同名的两只靠 `(塔, 贴图键)` 精确指定。
8. 每次改完必须：重跑建库 + 报**当前文件数**与**关键编号**；改名/删重复只改表，**不手改文件名**。

## 1. 每一步做什么

```
1) 读当前第 N 个文件的图      read_image：assets/library/monster/<编号>_<...>.png
2) 一句话描述图里是什么       形状、颜色、装备、姿势；不写"应该是"
3) 判名字                    图上 ≠ 游戏名 → 停，问用户
4) 判重复                    和已看过的哪张是同一张画？是 → 停，问用户删哪张
5) 回报                      描述 + 名字判定 + 重复判定（有问题就只到这一步）
6) 用户点头后再 N + 1
```

**看过一族的图之后，必须再做一步"整族并排对照"**（用户："里面这么多重复的看不出来"）：

- 把同一族（或同一个前缀）的所有图拼成**一张对照图**，按强弱排好，每格标 编号 / 名字 / power / 主色；
- 一张张单看是看不出成对结构的——两座塔各存一份，单个看都"很正常"；
- 成对/重复靠两个数确认：**可见差异**（通道差 >24 的像素占比）+ **不透明占比**
  （≈1.00 说明带棋盘底纹）。同一张画的两份：可见差异 0–35%，且常有一份带底纹；
- 判定顺序：先看是不是同一套画 → 再看是不是同一只怪 → 最后才按"重复"删。

## 2. 名字/归类/顺序写在哪（唯一真相）

| 要改什么 | 改哪里 |
|---|---|
| 某只怪的名字 | `chaita/library_names.py::ART_NAMES`：`(塔, 贴图键) → 中文名` |
| 名字的英文 | `chaita/library_names.py::NAME_ASCII`：中文名 → 英文词（名字那截，不重复种族词） |
| 种族英文 | `chaita/library_names.py::KIND_ASCII` |
| 删重复 | `chaita/library_names.py::ART_MERGES`：留下的那只 → `[并掉的 (塔,键)...]` |
| 按塔+键强制归类 | `chaita/library.py::RACE_BY_KEY` |
| 族内挪位置 | `chaita/library.py::KIND_PLACE`：`(要挪的几只, 锚点, "before"/"after")` |
| 整族挪位置 | `chaita/library.py::KIND_AFTER`：`{要挪的族: 排在哪个族后面}` |
| 还没定归属 | `chaita/library.py::PENDING_NAMES`：这些**移到最后**，不混进任何族 |

改名、删重复之后必须重建（编号会重排）：

```powershell
C:\Users\87790\.conda\envs\chaita\python.exe tools\build_library.py
C:\Users\87790\.conda\envs\chaita\python.exe -m unittest tests.test_library tests.test_names
```

## 3. 建库自动做的去重（不要重复劳动）

| 判据 | 阈值 | 说明 |
|---|---|---|
| 像素完全一样 | sha256 | 两座塔同一张图 |
| 同一张画（通道差 >24 才算不同） | ≤2% | 同一只怪两版导出；尺寸差 1–2 像素的先缩到同尺寸再比（只为比较，不落盘） |

判不出来的（同名但不同画、换色重绘）**不会自动并**，要人看、要用户点头。

## 4. "带底纹"怎么认 + 当前清单

图整块不透明（alpha > 200 的像素占比 ≥ 0.95）、四周一圈灰棋盘格 → 底纹烤进像素，**没有透明背景**。
盘上现有 **28 张**（编号会随重排变化，按 2026-11 这批）：

```
016 龙蝠 · 020 高级骷髅兵 · 038 鬼邪石 · 051 斗神·高巴 · 057 剑神·沙士
059 剑王 · 060 魔剑之凯撒 · 061 灵盾之柏奇 · 062 皇室枪兵 · 063 皇室剑士
064 血剑士 · 067 魔王 · 070 大魔王 · 071 魔法师元帅 · 075 魔神·些多
078 魔界之王·古顿 · 087 黄金龙 · 088 毒龙 · 089 巨型八爪鱼 · 097 箭神·法比
099 触手魔物 · 100 死灵大法师 · 101 死灵术士 · 102 生气灵 · 103 冥界矮人战士
104 魔眼 · 105 地狱马 · 106 血使者
```

处理方式（去底纹 / 删掉 / 先留着）**等用户定**，不许自己决定。

## 5. 当前状态（每次回报时更新）

```
文件数：110
待定（PENDING_NAMES）：魔神法师、铁守卫、灵武士   → 排在最后 108 / 109 / 110
还没定：060 的底纹、27 张底纹整体、067/068 是否并（按"不重复就不删"，不同画的一律不删）
已定过的：046 红衣大法师已删（留火炎大法师）；052 双手剑兵 → 剑士族（swordsman）排在骑士后；
          长袍魔法师族 = robed_mage，蓝/黄/红/黑，黄在红前
下次从：061_knight_e441.png（灵盾之柏奇）
```

## 6. 回报格式（照抄）

```
第 N 张：<文件名>
- 图里是什么：<形状/颜色/装备/姿势>
- 名字：<现名> ✓ / ✗（图上是什么、游戏里叫什么）
- 重复：跟第 K 张是同一张画 → 建议删哪张（等用户点头）/ 不是重复
```

---

## 6. owner 定的顺序（2026-10-28 定，**以这里为准**）

用户：现在记住这个顺序。这张表就是当前的编号顺序；manifest 的 order、
文件名编号、这张表三者一致。**重建会按旧的排序规则重排、把这张表冲掉** ——
要重建先把这张表当目标，重建完逐行核一遍。

| 编号 | 名字 | 文件 |
|---|---|---|
| 001 | 绿色史莱姆 | 001_slime_green_slime.png |
| 002 | 红色史莱姆 | 002_slime_red_slime.png |
| 003 | 黑色史莱姆 | 003_slime_black_slime.png |
| 004 | 史莱姆王 | 004_slime_slime_king.png |
| 005 | 白银史莱姆 | 005_slime_silver_slime.png |
| 006 | 黄金史莱姆 | 006_slime_gold_slime.png |
| 007 | 白银史莱姆王 | 007_slime_silver_slime_king.png |
| 008 | 黄金史莱姆王 | 008_slime_gold_slime_king.png |
| 009 | 邪眼史莱姆 | 009_slime_evil_eye_slime.png |
| 010 | 金角怪 | 010_slime_gold_horn.png |
| 011 | 尖角怪 | 011_slime_sharp_horn.png |
| 012 | 蝙蝠 | 012_bat_bat.png |
| 013 | 大蝙蝠 | 013_bat_big_bat.png |
| 014 | 红蝙蝠 | 014_bat_red_bat.png |
| 015 | 毒蝙蝠 | 015_bat_poison_bat.png |
| 016 | 龙蝠 | 016_bat_dragon_bat.png |
| 017 | 蓝色长袍魔法师 | 017_robed_mage_blue.png |
| 018 | 黄色长袍魔法师 | 018_robed_mage_yellow.png |
| 019 | 红色长袍魔法师 | 019_robed_mage_red.png |
| 020 | 黑色长袍魔法师 | 020_robed_mage_black.png |
| 021 | 骷髅 | 021_skeleton_skeleton.png |
| 022 | 骷髅兵 | 022_skeleton_skeleton_soldier.png |
| 023 | 冻死骨 | 023_skeleton_frozen_bone.png |
| 024 | 骷髅法师 | 024_skeleton_skeleton_mage.png |
| 025 | 中级骷髅兵 | 025_skeleton_mid_skeleton_soldier.png |
| 026 | 高级骷髅兵 | 026_skeleton_high_skeleton_soldier.png |
| 027 | 骷髅武士 | 027_skeleton_skeleton_warrior.png |
| 028 | 灵骷髅 | 028_skeleton_spirit_skeleton.png |
| 029 | 骷髅兵 | 029_skeleton_skeleton_soldier.png |
| 030 | 重生骷髅兵 | 030_skeleton_reborn_skeleton_soldier.png |
| 031 | 灵骷髅兵 | 031_skeleton_spirit_skeleton_soldier.png |
| 032 | 骷髅战士 | 032_skeleton_skeleton_fighter.png |
| 033 | 骷髅王 | 033_skeleton_skeleton_king.png |
| 034 | 骷髅巫师 | 034_skeleton_skeleton_wizard.png |
| 035 | 毒丧尸 | 035_zombie_poison_zombie.png |
| 036 | 丧尸 | 036_zombie_zombie.png |
| 037 | 烈焰丧尸 | 037_zombie_flame_zombie.png |
| 038 | 丧尸士兵 | 038_zombie_zombie_soldier.png |
| 040 | 守卫 | 040_guard_guard.png |
| 041 | 中级守卫 | 041_guard_mid_guard.png |
| 042 | 高级守卫 | 042_guard_high_guard.png |
| 043 | 斗神·高巴 | 043_guard_e380.png |
| 044 | 石头怪 | 044_rock_stone_rock.png |
| 045 | 铁怪 | 045_rock_iron_rock.png |
| 046 | 鬼邪石 | 046_rock_evil_stone.png |
| 047 | 史莱姆人 | 047_slime_man_slime_man.png |
| 048 | 四手史莱姆人 | 048_slime_man_four_arm_slime_man.png |
| 049 | 骑士 | 049_knight_knight.png |
| 050 | 近卫骑士 | 050_knight_bodyguard_knight.png |
| 051 | 铁骑士 | 051_knight_iron_knight.png |
| 052 | 强盾骑士 | 052_knight_strong_shield_knight.png |
| 053 | 剑神·沙士 | 053_knight_goldslime.png |
| 054 | 皇室枪兵 | 054_knight_royal_spearman.png |
| 055 | 皇室剑士 | 055_knight_royal_swordsman.png |
| 056 | 剑圣 | 056_knight_sword_saint.png |
| 057 | 双手剑兵 | 057_swordsman_two_hand_sword_soldier.png |
| 058 | 剑王 | 058_swordsman_sword_king.png |
| 059 | 弓兵 | 059_archer_archer.png |
| 060 | 箭神·法比 | 060_archer_e379.png |
| 061 | 精锐弓兵 | 061_archer_elite_archer.png |
| 062 | 魔法师首领 | 062_magician_magician_leader.png |
| 063 | 魔法师元帅 | 063_magician_magician_marshal.png |
| 064 | 魔王近卫兵 | 064_magician_demon_king_guard.png |
| 065 | 魔王 | 065_magician_demon_king.png |
| 066 | 黑衣魔王 | 066_magician_black_cloak_demon_king.png |
| 067 | 毒八爪鱼 | 067_octopus_poison_octopus.png |
| 068 | 闪光八爪鱼 | 068_octopus_flash_octopus.png |
| 069 | 八爪鱼 | 069_octopus_octopus.png |
| 070 | 巨型八爪鱼 | 070_octopus_giant_octopus.png |
| 071 | 大法师 | 071_mage_archmage.png |
| 072 | 火炎大法师 | 072_mage_flame_archmage.png |
| 073 | 极地法师 | 073_mage_polar_mage.png |
| 074 | 自己 | 074_hero_self.png |
| 075 | 假公主 | 075_princess_fake_princess.png |
| 076 | 痛苦魔女 | 076_princess_agony_witch.png |
| 077 | 仙子 | 077_fairy_fairy.png |
| 078 | 黑暗妖精 | 078_fairy_dark_sprite.png |
| 079 | 暗黑魔法师 | 079_undead_dark_magician.png |
| 080 | 死灵大法师 | 080_undead_undead_archmage.png |
| 081 | 死灵术士 | 081_undead_undead_warlock.png |
| 082 | 灵武士 | 082_undead_spirit_warrior.png |
| 083 | 魔王·格勒第 | 083_demon_king_vamp.png |
| 084 | 魔神·些多 | 084_demon_king_skeletonking.png |
| 085 | 巨龙 | 085_dragon_giant_dragon.png |
| 086 | 黄金龙 | 086_dragon_golden_dragon.png |
| 087 | 毒龙 | 087_dragon_poison_dragon.png |
| 088 | 触手植物 | 088_plant_tentacle_plant.png |
| 089 | 触手魔物 | 089_plant_tentacle_monster.png |
| 090 | 魔神武士 | 090_demon_god_demon_god_warrior.png |
| 091 | 魔神法师 | 091_demon_god_demon_god_mage.png |

空号：[39]（039 是删掉的那张重复图，没前移）。
