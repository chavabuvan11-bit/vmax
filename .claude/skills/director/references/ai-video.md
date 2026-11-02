# Directing AI Video Models

How to turn a shot list into prompts that video models execute well, and
how to keep a sequence consistent. Model capabilities change monthly. Treat
the model notes as a starting point, and check current docs when the user
names a model and you have a way to look.

Contents
1. Pipeline
2. Prompt anatomy
3. Image-to-video vs text-to-video
4. Consistency
5. Camera language models understand
6. Failure modes → fixes
7. Model notes (verify)
8. Prompt block format

---

## 1. Pipeline

1. **Bibles first**: character, location and style strings fixed before any generation.
2. **Start frames**: generate a production-quality still per shot (image model), in the style suffix. Iterate stills, which are cheap, rather than videos, which are not.
3. **Animate**: image-to-video with a motion-only prompt. Optionally first+last frame for precise landings.
4. **Select & extend**: generate 2–4 takes per shot; pick on performance and physics, not just beauty. Extend or chain from the last frame when a shot must run longer than one clip.
5. **Edit, sound, grade**: assemble to the edit plan; unify with one grade pass and texture (grain/halation) so clips from different generations sit together.
6. **Match**: run `deconstruct.py` + `compare.py` against the reference, then fix the worst gap and repeat.

## 2. Prompt anatomy

Order matters less than completeness, but this order reads well to most models:

```
[Shot size + angle] of [subject: bible string] [doing ONE action] in [location: bible string],
[light: direction, quality, colour, motivation], [camera: move, speed, direction],
[lens: focal, DOF], [style suffix: grade, texture, aspect], [mood/pace word].
```

Example:
> Low-angle medium close-up of Mara (late 20s, cropped black hair, olive
> rain jacket, silver ring on left index finger) turning her head toward
> the sound, on a wet rooftop at night; hard magenta neon key from camera-left,
> cool cyan fill from city haze, rain catching the light; slow push-in, about
> 10% closer over 5 seconds; 50mm, shallow depth of field; teal-magenta grade,
> crushed blacks, fine film grain, anamorphic 2.39:1; tense, held breath.

Write physics and light relationships ("neon reflections smear across the
puddle as she steps"). Models reason better from cause and effect than from adjectives.

## 3. Image-to-video vs text-to-video

- **I2V (default for realism)**: the image fixes composition, identity, light
  and grade. The text should describe **only motion and change**: the action,
  the camera move, what's different at the end. Re-describing the image wastes
  tokens and can fight the frame.
- **T2V**: fine for abstract, stylised, establishing, or exploratory shots;
  weaker for identity consistency across a sequence.
- **First + last frame**: when the end state matters (product lands in hand,
  door closes, logo resolves). Keep the two frames plausibly reachable in the clip length.
- **Reference images / elements** (where supported): attach character sheet and
  location plates to every shot that features them.

## 4. Consistency

- One immutable descriptor string per character/location; paste verbatim.
- Character sheet: front, 3/4, profile, full body, neutral light + profile light.
- Wardrobe described with colour **and** material ("matte olive nylon rain jacket").
- Keep lens/light/grade suffix identical across a scene; change it deliberately per scene.
- Same seed for takes of the same shot when the tool exposes it.
- Chain shots: use the last frame of shot N as the start frame of shot N+1 for continuous action.
- Unify in post: one grade, one grain, one aspect for the whole cut.

## 5. Camera language models understand

Reliable: static/locked-off, slow push-in / dolly in, pull-out / dolly out,
pan left/right, tilt up/down, tracking shot alongside, orbit / arc around,
crane up / down, handheld, drone aerial / flyover, FPV, zoom in/out, rack
focus, top-down, low angle, over-the-shoulder, POV.

Make it concrete: direction, speed, distance, end framing. "Slow orbit 90°
clockwise around the subject, ending on her profile" beats "dynamic camera".

Don't combine contradictory moves in one shot. Two compatible moves (push-in +
slight pan to follow) are fine; three is asking for chaos.

## 6. Failure modes → fixes

| Failure | Fix |
|---|---|
| Face/identity drifts mid-shot | I2V from a strong start frame; shorter clip; less head rotation; reference image; avoid occlusion |
| Morphing / melting during fast action | generate slower ("slow motion") and speed up in edit; one action; simpler background |
| Hands/fingers garbled | keep hands out of focus or out of frame, give them a simple grip, cut to an insert from a dedicated generation |
| Gibberish text/signage | no legible text in prompts; add text in post |
| Physics fails (liquids, cloth, collisions) | describe cause → effect; shorter clip; pick takes; use the model known for physics |
| Camera drifts or ignores the move | state move + speed + end frame; first/last frame control; remove competing motion words |
| Too much happening | split into separate shots (one action each) and cut between them |
| Plastic/CG look | specify lens, light motivation, skin texture, grain; avoid "8k ultra HD hyperreal" tag soup |
| Clips don't match each other | identical style suffix; one grade + grain pass in post; same aspect |
| Crowds/background people warp | defocus them, reduce count, or plate them separately |
| Lip-sync off | use a model/tool with native audio or a dedicated lip-sync pass; keep the face frontal-ish and well lit |

## 7. Model notes (verify; this landscape moves fast)

Tendencies reported at the time of writing. Check the vendor's current
docs for clip length, aspect ratios, audio, and control features before
committing a plan.

| Family | Often strong at | Prompting notes |
|---|---|---|
| Google Veo | photoreal, slow aesthetic shots; native audio incl. dialogue and SFX in recent versions | can describe sound and spoken lines in the prompt; be explicit about camera |
| OpenAI Sora | coherent scenes, physics, native audio in recent versions | natural-language scene direction; multi-shot within one prompt possible in newer versions |
| Kling | human motion, physics, action; start/end frame; motion control features | supports negative prompts; good I2V workhorse |
| Runway (Gen-4 family) | I2V with consistent references, stylised and photoreal | prompt the motion, not the image; uses reference images for consistency |
| Luma (Ray family) | fluid camera moves, fast cinematic energy | keyframes for start/end control |
| ByteDance Seedance | multi-shot sequences, smooth camera, prompt adherence | can describe several shots in one prompt in newer versions |
| MiniMax Hailuo | expressive human motion, dramatic camera | concise prompts with clear camera instruction |
| Wan / LTX (open weights) | local control (ComfyUI), LoRAs for style/character | needs more explicit prompts; good for fine-tuned consistency |

If the user has a generation API wired up (muapi.ai scripts, fal, Replicate,
a vendor SDK, ComfyUI), hand it the per-shot prompt blocks as-is; the format
below maps onto any of them.

## 8. Prompt block format

```markdown
### Shot 07: "She hears it" · 0:21–0:24 (3.0 s)
- Size/angle: MCU, low angle · Lens: 50mm, shallow · Move: slow push-in ~10% over 3 s
- Action (one): Mara turns her head toward off-screen sound, camera-left
- Light: hard magenta neon key camera-left, cyan haze fill; rain
- Continuity: screen direction L→R kept; jacket hood down; ring visible; follows shot 06's eyeline

**Start frame**
> <full image prompt + style suffix>

**Motion (I2V)**
> Mara slowly turns her head to her right toward an off-screen sound; rain keeps falling; camera pushes in gently, ending on a tight MCU of her profile.

**End frame (optional)**
> <only if the model supports it and the landing matters>

**Avoid**
> extra people, text, hand close-ups, face morphing, fast camera shake

**Model**: Kling (I2V, 5 s, trim to 3 s) · takes: 3 · seed: reuse from shot 06
```
