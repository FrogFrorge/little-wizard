# tools

The Python scripts behind the final version of Little Wizard: the characters, the Blueprint
changes, the sound and music, the interface texts and the videos. All but one were written by
Claude Code in rounds 1–21 (see the [development log](../docs/DEVLOG.md)); `wizard_pose_math.py`
dates from the earlier Codex phase. They were written for one machine (Windows, Blender 5.2 and
Unreal Engine 5.8 with the game project) and are published to show how the project was built;
each file starts with a docstring that says what it does and how to run it.

Scripts named `r11_*` to `r21_*` belong to rounds 11 to 21; the character pipeline (`*_v5.py`)
has been used in every round since the models were rebuilt as version 5.

## 3D characters (Blender, `blender -b -P <script> -- <kind>`)

| Script | What it does |
|---|---|
| `build_wizard_models_v5.py` | Builds one wizard (fire, ice, wind, lightning) from scratch: body, clothes, head, rig, actions, renders, FBX. `-- <kind> head` renders only the head for quick look development |
| `wizard_hair_v5.py` | Heads and hair: the face as a smooth union of ellipsoids with carved eye sockets, eyes / lids / lashes with Blink and A-I-U-E-O morph targets, ears, sculpted hair clumps and hair cards, the per-character style tables (`STYLES`) |
| `wizard_outfit_v5.py` | Shoes, garments, sleeves, trims and appliqués, accessory physics chains |
| `wizard_fabric_v5.py` | Tiling fabric detail textures (weave, prints, wrinkles) per wizard |
| `wizard_pose_math.py` | Small vector helpers shared by the build |
| `validate_wizard_v5.py` | FBX round trip, bone and influence checks, eyelid coverage when closed, hair chains |
| `render_compare_v5.py`, `finalize_v5.py`, `package_v5.py` | Same-camera renders, the turnaround sheets as overlays in the .blend, comparison sheets |
| `r21_headcmp.py` | Turnaround sheet vs head render side by side at the same scale (round 21) |

## Unreal Engine (commandlet or editor Python)

| Script | What it does |
|---|---|
| `r11_bp.py` | Helpers for editing Blueprint graphs from Python (nodes, pins, links, variables, functions, layout, compile) |
| `import_wizard_models_v5.py` | Imports the four models, builds one Animation Blueprint per wizard (pose copy from the mannequin, two-bone foot IK, per-bone AnimDynamics for hair and cloth, blink and mouth morphs), wires the character |
| `r11_actions_pose.py`, `r11_actions.py` | The wizards' own casting, guarding and hovering poses, keyed into animation sequences |
| `r11_traits.py`, `r12_char_b.py` | Trait changes: Gale's speed, Neve's hover, each wizard keeping only their own abilities, wizard switching in practice mode (F1–F4) |
| `r11_ultimates.py`, `r12_ult_a.py` | The 16 ultimates: the character's delivery × the magic's payload |
| `r11_vfx.py`, `r11_cute_shapes.py` | Cute magic effects: sprite shapes drawn in material code, Niagara systems |
| `r13_wire.py`, `r14_wire.py`, `r13_import.py` | Ultimate presentation (wind-up sounds, HUD cut-in card), second-press effects, importing the sound |
| `r14_ui.py`, `r15_lang.py`, `r15_texts.py`, `r16_fonts.py` | The bright menu theme, the four-language text system and its fonts |
| `r13_cutin_art.py`, `r15_cutin_art.py` | The ultimate cut-in cards, one per wizard and language |
| `r20_death_fall.py` | The physics knock-out fall (direction of the blow, rigid-body topple, gravity drop) and the tunable ultimate chance |
| `r11_compile_check.py` | Compiles every Blueprint and reports problems |
| `r11_test_ultimates.py`, `r15_lang_test.py`, `r20_fall_test.py` | Play-in-editor tests |

## Sound and music (Python + NumPy)

| Script | What it does |
|---|---|
| `r13_synth.py` | Synthesis building blocks: oscillators with band-limited steps, FM, noise, envelopes, filters, reverb, limiter |
| `r13_instruments.py` | Instruments built from them (celesta, harp, strings, brass, taiko, synth leads, …) |
| `r13_sfx.py` | All 47 sound effects |
| `r13_music.py` | The 7 music pieces (menu, duel and one per arena), written bar by bar, seamless loops |

## Videos

| Script | What it does |
|---|---|
| `r20_intro.py` | Captures the character introduction footage in play-in-editor: fixed 1/30 s time step, a screenshot per frame, the game's sound recorded in step, each wizard in their own arena |
| `r20_intro_post.py` | Title / character / closing cards, the per-language ultimate cut-in drawn on the game's own clock, crossfades, music, MP4 |
| `r20_battle.py` | A real 1v1v1v1 match played by four bots, seen through the game's third-person camera, with a close-up of every knock-out; also a statistics mode used to tune the ultimate chance |
| `r20_battle_post.py` | Title card, health bars, kill feed, banners, music, MP4 |
| `r19_intro_post.py`, `r19_battle_post.py`, `r11_video_post.py`, `r13_video_post.py` | Shared pieces of the post-production (typesetting, audio mixing) |
| `r11_video_encode.py` | Encodes frames and sound to MP4 with Blender's FFmpeg |
