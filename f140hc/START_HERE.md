# Start here: continuing the F140HC Blender model in a new chat

Paste the block below into the new chat as your first message. Attach the reveal video
(`reveal.mp4`) if you still have it. Some measurements came from it, but the work can carry
on without it.

---

I'm continuing a project from a previous chat. Repo: `chavabuvan11-bit/vmax`, branch
`claude/magical-bell-4e0g8c`. Develop and push only on that branch, and don't open a PR unless
I ask.

The project is a photorealistic 1:1 Blender model of the Ferrari Daytona SP3's F140HC 6.5 L V12,
including the gearbox and exhaust, with fully working internals. It has to be right down to
the bolt.

1. Read `f140hc/HANDOVER.md` end to end before doing anything. It covers:
   - my requirements
   - setup
   - conventions
   - the reference photos and solved cameras
   - the methods that work
   - the pitfalls already hit
   - the current priority list
2. Run setup: `bash f140hc/tools/setup_refs.sh`, then set `F140_REFS` and `F140_HDRI` as the
   script prints them.
3. Check the starting state: `verify.py` must print PASS and `tools/sanity.py` must print
   SANITY: PASS.
4. Carry on with the priority list in HANDOVER section 7.

Rules I care about:

- Use several reference images per part, never just one.
- Research individual parts online.
- Run the common-sense checks on every part (`sanity.py`: nothing floating, no loose tube ends,
  bolts seated, no clashing tubes).
- Back-project traces through the solved cameras instead of flat pixel-to-mm mappings.
- Commit and push often, and keep HANDOVER.md current.
- Be direct with me and push back when I'm wrong.

---

## What the new chat gets from the repo

| Path | What it is |
|---|---|
| `f140hc/HANDOVER.md` | The full handover. Read it first. |
| `f140hc/f140hc_build.py` | The model. Everything derives from the `P` table at the top. |
| `f140hc/verify.py` | Mechanism checks plus reference renders. |
| `f140hc/tools/` | Checks, camera solving, measuring, tracing and rendering scripts. |
| `f140hc/tools/setup_refs.sh` | Recreates the Python/Blender environments and downloads the photos and HDRIs. |
| `f140hc/reference_data/` | Solved cameras, picks, specs, measurements, product JSON. |

The tools in `f140hc/tools/` include:

- `sanity.py`: common-sense checks
- `bundle_adjust.py`: joint camera solve
- `solve_header_depth.py` and `dump_headers.py`: exhaust tube depth solver
- `raycast_pick.py`: which part sits under a photo pixel
- `render_section.py` and `compare_section.py`: render through a solved camera and compare with
  the photo

## Not in the repo

- **Amalgam photos and HDRIs:** downloaded by `setup_refs.sh`.
- **The reveal video:** you uploaded it, so the new chat needs it uploaded again.
  - The setup script prints the ffmpeg command for extracting frames.
  - Its cameras and picks are already saved in `reference_data/`, so the video is only needed
    for new measurements.
