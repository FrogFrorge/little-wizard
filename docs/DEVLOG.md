# 開發紀錄 Development log

小小魔法師是一輪一輪做出來的：每一輪沈家樂試玩、看影片、提出意見，AI 程式助理依意見修改腳本、重新生成並驗證。
Little Wizard was built in rounds: each round Sem Jia Le played the game and watched the test videos, gave feedback,
and the AI coding assistants changed the scripts, rebuilt everything and verified it.

| 輪 Round | 內容 | What changed |
|---|---|---|
| 1–9 | 遊戲系統（對戰、競技場、介面流程、特效、音效）；角色模型從第 1 版做到第 5 版：程式化頭部、依三視圖校正比例、眼皮與眨眼改用變形目標、女生的頭髮改成絲滑髮片、自然的肩膀與手臂 | Game systems (matches, arenas, UI flow, effects, sound); character models from version 1 to 5: procedural heads, proportions matched to the turnaround sheets, morph-target blink, silky hair cards for the girls, natural shoulders and arms |
| 10 | 遊戲裡的頭髮與綁帶物理、眨眼與施法張嘴、腳步 IK、布料織紋與小星星印花、面數減少 28–38% | In-game hair and strap physics, blinking and casting mouths, foot IK, fabric weave and star prints, 28–38% fewer triangles |
| 11 | 角色與魔法分開（每位魔法師都能用四種魔法）、可愛的魔法特效、角色自己的動作、16 種大招 | Character and magic separated (every wizard casts all four magics), cute magic effects, the wizards' own actions, 16 ultimates |
| 12 | 角色名字（布萊茲、妮芙、蓋爾、沃爾妲）、更沉穩的頭髮、會擺動的衣擺、頭看向準星 | Names (Blaise, Neve, Gale, Volta), calmer hair, swinging coat panels, heads looking at the crosshair |
| 13 | 全新的合成音效與 7 首配樂、大招起手音效、大招立繪卡 | All-new synthesized sound effects and 7 music pieces, ultimate wind-up sounds, ultimate cut-in cards |
| 14 | 普攻二段的音效與特效、插畫立繪用在所有介面、明亮的米白金色選單 | Second-press sounds and effects, the illustration used for every portrait, bright cream-and-gold menus |
| 15–17 | 四種語言（英、繁中、日、法）與各自的字型：霞鶩文楷配 Tinos、Noto Sans JP、Tinos | Four languages (EN, ZH, JA, FR) with their own fonts: LXGW WenKai with Tinos, Noto Sans JP, Tinos |
| 18–19 | 每位角色的完整示範影片、四種語言的介紹影片、電腦對戰影片 | Full demo video per wizard, introduction videos in four languages, a bot battle video |
| 20 | 物理倒地（依被打方向、空中被擊倒會落地）、大招機率由 10% 調成 5%（模擬 15 場比賽決定）、影片全部重拍成正式介紹影片，對戰改用遊戲本身的第三人稱鏡頭並加入擊倒特寫 | Physics knock-outs (direction of the blow, falling to the floor when hit in mid-air), ultimate chance 10% → 5% (decided from 15 simulated matches), every video remade as a real introduction, the battle in the game's own third-person camera with knock-out close-ups |
| 21 | 模型修飾：眼睛稍大、沃爾妲的頭髮更蓬並加長瀏海、白色衣物改為溫暖的米白；作品集整理 | Model polish: slightly larger eyes, fuller hair and a longer fringe for Volta, warm off-white garments; this portfolio |

## 大招機率的模擬結果 Ultimate chance, simulated

四位電腦 AI 混戰，每種機率 5 場（Four bots, five matches per chance）：

| 機率 Chance | 全場平均 Every (whole match) | 每位角色平均 Per wizard | 有放到大招 Wizards with one |
|---|---|---|---|
| 10% | 5.9 s | 17 s | 19 / 20 |
| **5%** | **8.9 s** | **25 s** | **17 / 20** |
| 2.5% | 17.8 s | 55 s | 10 / 20 |

## 倒地的物理 The knock-out fall

身體視為從腳底翻倒的剛體：θ'' = (3g ÷ 2L)·sin θ（g = 980 cm/s²，身高 L ≈ 140 cm），被打中時給一個推力，
著地反彈 25%；在空中被擊倒時，先往下找地面，再用重力加速度落下。

The body is a rigid body toppling about its feet: θ'' = (3g / 2L)·sin θ (g = 980 cm/s², L ≈ 140 cm), pushed by the blow,
bouncing back 25% on landing; knocked out in mid-air, it first traces the floor below and then drops with gravity.
