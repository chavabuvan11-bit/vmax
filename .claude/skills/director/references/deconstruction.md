# Visual Deconstruction & Style Reference

How to read a reference like a DP, editor and colourist, and how to write
what you find as a profile someone else (or a video model) can execute.

Contents
1. Reading order
2. The checklist: what to read and how to read it from stills
3. Evidence discipline
4. Style DNA profile template
5. Multi-reference synthesis

---

## 1. Reading order

1. `report.md` skeleton: runtime, aspect, ASL, pace curve, look line, motion mix, tempo/sync.
2. `barcode.png`: the colour arc. Does the grade shift by act, by location, or hold?
3. Every contact sheet, in order. First pass: story and structure only. Second pass: craft.
4. Start/mid/end frames for long shots: the move, and where it lands.
5. `transcript.txt`: hook line, voice, words-per-minute, where dialogue sits against cuts.
6. Platform description/chapters: stated intent, gear lists, credits (useful, but verify on screen).

## 2. The checklist

For each area: what to look for, and how stills reveal it.

### Structure & intent
- What is it (music video, ad, short, essay, vlog, trailer)? Who's it for? What should the viewer feel at the end?
- **Hook**: what happens in the first 1–3 s? Image, line, sound, question?
- Beats/acts: where does the pace curve rise, fall, spike? Do they line up with story turns?
- Ending: button, loop, call to action, cut to black?

### Rhythm & editing
- ASL, median, range, cuts/min (measured). Is the median much lower than the mean? Then a few long holds anchor many quick cuts. That's a signature.
- Pace curve shape: flat, accelerating build, breathing (fast/slow alternation), climax spike.
- Cut types (look at adjacent tiles): hard cut, match cut (shape/motion/colour rhymes across the cut), jump cut (same framing, time skipped), smash cut, cutaway/insert, cross-cutting, whip-pan/hidden cut, dissolve, flash/strobe frames, cut to black.
- Cutting on action vs on stillness; on beat (measured "cuts on onset" well above chance) vs on phrase vs free.
- Speed: slow motion (smooth motion blur-free fluid movement, often hair/fabric/liquid), speed ramps, time-lapse, freeze frames.

### Camera: position & movement
- **Shot sizes** distribution: EWS / WS / FS / MS / MCU / CU / ECU / insert. Count from the sheets.
- **Height & angle**: eye level, low (horizon low in frame, ceilings visible), high, overhead/top-down, Dutch.
- **Movement** (measured mix, then verify): locked-off, pan, tilt, dolly/push, truck, pedestal, crane/jib, handheld (shake), gimbal/Steadicam (floating, no shake, smooth arcs), drone (altitude, sweeping parallax), orbit, zoom (perspective doesn't change, background scales with subject), snap zoom, whip pan.
- Movement *motivation*: does the camera follow action, anticipate it, reveal, or drift independently?

### Lens & optics
- **Focal length** cues: wide (<28 mm): exaggerated depth, converging lines, faces bulge near frame edge, lots of background. Normal (35–50): natural proportions. Long (85+): flattened depth, background looks big and close to subject, faces flattering, narrow background slice.
- **Depth of field**: how many planes are sharp? Bokeh size, shape (round vs oval = anamorphic, cat's-eye at edges = vintage fast glass).
- **Lens character**: anamorphic (horizontal blue/amber streak flares, oval bokeh, slight edge distortion, 2.39:1), vintage (veiling glare, low contrast, soft corners, swirl), modern clinical (sharp to the edges, neutral flare).
- **Focus behaviour**: rack focus, split diopter, deep focus, focus breathing.

### Composition
- Placement: centred/symmetrical, rule of thirds, short-siding (looking into the near edge = tension), headroom, lead room.
- Depth layering: foreground objects ("dirty" frames), midground subject, background separation.
- Negative space, frames within frames, leading lines, horizon placement.
- Aspect ratio & letterbox (measured active aspect: 1.78 = 16:9, 1.85, 2.0, 2.39 scope, 1.0 square, 0.56 vertical).

### Light
- **Key direction**: read catchlights (position = clock face on the eye; shape = source: square softbox, ring, window, round bulb) and the nose shadow (Rembrandt triangle, loop, butterfly, split).
- **Quality**: hard (crisp shadow edge) vs soft (wrapped gradient). Size of source relative to subject.
- **Contrast ratio**: compare lit and shadow side of faces: ~2:1 flat/commercial, ~4:1 dramatic, 8:1+ noir.
- **Motivation**: is there a visible source (window, practical lamp, neon, screen, fire)? Is the light consistent with it?
- **Separation**: rim/back light, hair light, background lit or dark.
- **Time & atmosphere**: golden hour (long warm shadows), blue hour, overcast, night exterior (mixed colour temps), haze/smoke (visible beams, lifted blacks in the distance).
- **Colour of light**: mixed temperatures (warm practicals vs cool ambience) or single-source purity.

### Colour & grade
- Measured: mean luma (key), contrast, black point (crushed <0.01, matte >0.07), white point (clipped >0.97, rolled-off <0.8), saturation, warmth (R−B), tint (G−RB), split tone (shadow vs highlight bias), palette.
- Look at skin: natural, pushed warm, desaturated, orange-and-teal (skin protected while everything else shifts toward cyan)?
- Palette strategy: complementary, analogous, monochrome, single accent colour, colour-coded characters/locations.
- Does the barcode change by section? (flashback grade, location coding, a colour arc that tracks emotion)

### Texture & capture
- Grain (fine digital noise vs organic film grain), halation (red/orange glow around bright edges = film or emulation), bloom/diffusion (Pro-Mist glow on highlights), gate weave, light leaks, VHS/digicam artifacts, sharpening halos.
- **Shutter / motion blur**: natural blur on moving hands = ~180°; staccato crisp action = narrow shutter (think battle scenes); smeared streaks = wide shutter or long exposure.
- Frame rate feel: 24 fps cinema cadence, 30/60 video-smooth, stepped/animated-on-twos.
- Capture vibe: cinema camera, phone, GoPro (wide barrel, deep focus), security cam, film stock.

### Production design, wardrobe, casting, performance
- Palette of sets and wardrobe (often where the "grade" really comes from).
- Clutter vs minimal, period, location type, practical lights in frame.
- Performance style: naturalistic, deadpan, direct-to-lens, choreographed.

### Sound
- Measured: tempo, onsets/min, loudness range (compressed vs dynamic), silence %, speech rate.
- Music role: wall-to-wall, drops, silence before impact. Sound design: whooshes on cuts, risers, hits, foley detail, room tone.
- Dialogue/VO placement: J-cuts (sound leads picture) and L-cuts (sound trails), VO over montage, on-camera.

### Graphics & typography
- Titles, lower thirds, captions (burned-in style matters for Shorts/Reels), kinetic type, overlays, frames/UI.

## 3. Evidence discipline

Write every claim as **evidence → inference** and tag its source:

- `[measured]` from report/analysis.json.
- `[seen]` visible in a named frame/sheet (cite shot numbers).
- `[inferred]` reasoning from what's seen (say from what).
- `[stated]` from description/credits; keep it unless the frames contradict it.

If something can't be determined (e.g. sound when there's no audio, real focal
length with no reference objects), write "unknown". Don't round a guess up into a fact.

## 4. Style DNA profile template

Copy this into `style-profiles/<slug>.md` and fill it in.

```markdown
# Style DNA: <title>

Source: <url or file> · Runtime <m:ss> · Analysed <date> · Shots <n>
One-line identity: <what this looks and feels like in one sentence>

## Intent & structure
- Format / audience / platform:
- Hook (0–3 s):
- Beat map: <time → beat → what changes in picture/sound>
- Ending:

## Rhythm
- ASL <x s> · median <y s> · <z> cuts/min · longest hold <s> [measured]
- Pace curve: <shape, where it accelerates/breathes> [measured]
- Cut vocabulary: <hard / match / jump / whip / dissolve / flash…, with shot refs> [seen]
- Music sync: <cuts on onset % vs chance; on downbeats or phrases> [measured]

## Camera
- Shot-size mix: <e.g. 40% CU, 30% MS, 20% WS, 10% inserts> [seen]
- Height/angle habits:
- Movement grammar: <measured mix + how/why it moves> [measured+seen]
- Lens: <focal range, DOF, character (anamorphic/vintage/clean)> [inferred from …]

## Composition
- Placement & symmetry habits:
- Depth & foreground:
- Aspect / letterbox: [measured]

## Light
- Key: <direction, quality, ratio> [inferred from catchlights/shadows in shots …]
- Sources & motivation:
- Separation / background:
- Time of day & atmosphere:

## Colour & texture
- Look: <report look line, corrected by eye> [measured+seen]
- Black/white handling: <crushed / matte / clipped / rolled> [measured]
- Split tone & skin: [measured+seen]
- Palette: <hex swatches + where they live (wardrobe, set, light)>
- Arc: <how the barcode changes> [measured]
- Texture: <grain, halation, bloom, shutter feel, frame-rate feel> [seen]

## Design, wardrobe, performance

## Sound
- Music: <genre, tempo, role> · Design: <whooshes, hits, silence> · Dialogue/VO: <wpm, placement>

## Graphics & type

## Signature moves (the 3–6 that make it *this*)
1. <specific, repeatable, shot-referenced>
2.
3.

## Rules & anti-rules
- Always:
- Never:

## Prompt kit
- Style suffix (paste after every image/video prompt):
  `<lens, light, grade, texture, aspect in one compact line>`
- Negative / avoid:
  `<the things that would break this look>`
- Example start-frame prompt (one hero shot in this style):
- Example motion prompt (one signature move):

## Confidence & gaps
- High confidence: …
- Unverified / unknown: …
```

## 5. Multi-reference synthesis

When the user gives several references, profile each, then add:

```markdown
# Synthesis: <name>
- Shared DNA (the actual style): <traits present in all/most, with which refs>
- Divergences (choices to make): <trait: ref A does X, ref B does Y → recommendation>
- Recommended blend: <one paragraph, opinionated>
- Combined prompt kit: <suffix + negatives>
```

Pick a side on the divergences. "It depends" isn't a direction.
