# vmax

## Director skill

`.claude/skills/director/` is a Claude skill that works as director,
cinematographer and editor:

- **Deconstruct**: give it a video link or file and it measures the cutting rhythm
  (shots, average shot length, pace curve, cuts on the beat), exposure and
  colour grade (key, contrast, black/white points, warmth, split tone, palette),
  camera-motion mix (locked-off, pan, tilt, push-in, handheld), aspect and
  letterboxing, and speech rate. It also writes contact sheets and a colour
  barcode so Claude can *look* at every shot. Claude then writes a "Style DNA"
  profile: evidence, inference, signature moves, and a prompt kit.
- **Direct**: turns a brief and a profile into a treatment, character/location/style
  bibles, a shot list, per-shot start-frame and motion prompts for AI video
  models, and an edit plan.
- **Match**: scores a generated cut against the reference (`compare.py`) and
  lists what to change.

### Use it

- **Claude Code, this repo**: it loads automatically as a project skill. Say
  "break down this video: <link>" or "/director".
- **Claude Code, everywhere**: `cp -r .claude/skills/director ~/.claude/skills/`
- **claude.ai**: zip the `director` folder and upload it under Settings → Capabilities → Skills.

Requires `ffmpeg`, Python 3 with `numpy` and `Pillow`, and `yt-dlp` for links
(`pip install numpy pillow yt-dlp`).

```bash
python3 .claude/skills/director/scripts/deconstruct.py "<url-or-file>" -o deconstruct/<name>
python3 .claude/skills/director/scripts/compare.py deconstruct/<ref>/analysis.json deconstruct/<mine>/analysis.json
```

### Reference videos

Three YouTube references were requested. They haven't been analysed yet,
because YouTube was unreachable from the environment the skill was built in.
See `.claude/skills/director/style-profiles/README.md` for the queue and the
command to run them.

### Credits

The directing half draws on ideas from two MIT-licensed community skills:
SamurAIGPT's *AI Cinema Director* (`generative-media-skills`, intent→craft
mapping, prompt formula) and Aditya Raj's *ai-cinematic-video-director*
(start-frame-first, one action per shot, character sheets). No code was
copied; the deconstruction tooling is original.
