# Development log

**English** · [繁體中文](DEVLOG.zh-TW.md)

Little Wizard was made in about a month, in three phases. Sem Jia Le designed and directed the game throughout; after the prototype, AI coding agents wrote the code and built the assets, and every build was reviewed by playing it and watching test videos.

## Phase 1: the prototype (late September 2026)

Sem Jia Le designed the game and built the first playable version in Unreal Engine Blueprints, step by step with ChatGPT:

- a third-person wizard in an arena;
- casting the fireball and the other three orbs, each with its first form and its second-press effect;
- the wizard and the magic as two separate choices (the `E_WizardType` and `E_SpellType` enumerations);
- each wizard's traits.

## Phase 2: early development with OpenAI Codex (October 2–12)

Under Sem Jia Le's direction, Codex added cooldowns and the ultimate system, the match flow and the menus, aiming and the HUD, the first magic effects and ultimates, the arenas and their music, the first sound effects, and the first four versions of the 3D characters, built from turnaround sheets generated with ChatGPT.

## Phase 3: rounds 1–21 with Claude Code (October 13–25)

In each round Sem Jia Le played the latest build, watched the test videos and gave feedback; Claude Code changed the scripts, rebuilt everything and checked it.

| Round | What changed |
|---|---|
| 1–9 | The characters rebuilt from scratch (version 5): procedural heads, proportions matched to the turnaround sheets, eyelids that blink with morph targets, silky hair cards for the girls, natural shoulders and arms, outfits with physics straps |
| 10 | Hair and strap physics in the game, blinking and mouth shapes while casting, foot IK, fabric weave and star prints, 28–38% fewer triangles |
| 11 | Cute new magic effects, the wizards' own casting poses, Neve's staff, and 16 ultimates (the wizard decides the delivery, the magic decides the payload); wizard switching in practice mode |
| 12 | Names (Blaise, Neve, Gale, Volta), calmer hair, swinging coat panels, heads that follow the crosshair, fixes to traits and ultimates |
| 13 | All-new synthesized sound effects and seven music pieces, ultimate wind-up sounds, ultimate cut-in cards |
| 14 | Sounds and effects for the second press, the illustration as every portrait, bright cream-and-gold menus |
| 15–17 | Four interface languages (English, Traditional Chinese, Japanese and French), each with its own fonts |
| 18–19 | A demonstration video for each wizard, introduction videos in four languages, a bot battle video |
| 20 | Physical knock-outs (falling the way the blow pushed, dropping to the floor if hit in mid-air); ultimate chance cut from 10% to 5% after simulated matches; every video remade as a proper introduction, with the battle in the game's own third-person camera and knock-out close-ups |
| 21 | Model polish (slightly larger eyes, fuller hair and a longer fringe for Volta, warm off-white garments) and this portfolio |

## Choosing the ultimate chance

Four bots fought five matches at each chance:

| Chance | An ultimate every (whole match) | Per wizard | Wizards who got one |
|---|---|---|---|
| 10% | 5.9 s | 17 s | 19 / 20 |
| **5%** | **8.9 s** | **25 s** | **17 / 20** |
| 2.5% | 17.8 s | 55 s | 10 / 20 |

At 5%, ultimates stay special while almost every wizard still gets one; at 2.5%, half of the wizards never do.

## The knock-out fall

The body is treated as a rigid body toppling about its feet: θ'' = (3g / 2L) · sin θ, with g = 980 cm/s² and a height of L ≈ 140 cm. The blow pushes it in the blow's direction, and it bounces back 25% on landing. A wizard knocked out in mid-air first traces the floor below, then drops to it under gravity.
