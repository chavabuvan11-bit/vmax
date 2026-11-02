# Style profiles

Saved Style DNA profiles live here, one file per reference (`<slug>.md`),
plus `synthesis-<name>.md` when several references are blended.
Format: `references/deconstruction.md` §4.

## Queue: not analysed yet

These were requested but couldn't be downloaded when the skill was built:
the cloud environment's network policy refused `www.youtube.com`. Nothing
about their content has been written down, deliberately: a profile has to
come from the footage.

| Slug | Source | Status |
|---|---|---|
| `ref-SkSrX2rM8jk` | https://www.youtube.com/watch?v=SkSrX2rM8jk | pending: host blocked |
| `ref-XHf6PUsb1eE` | https://www.youtube.com/watch?v=XHf6PUsb1eE | pending: host blocked |
| `ref-1UE_RnIbt4c` | https://www.youtube.com/watch?v=1UE_RnIbt4c | pending: host blocked |

To run them (somewhere YouTube is reachable, e.g. Claude Code on your own machine):

```bash
for id in SkSrX2rM8jk XHf6PUsb1eE 1UE_RnIbt4c; do
  python3 .claude/skills/director/scripts/deconstruct.py "https://www.youtube.com/watch?v=$id" -o "deconstruct/ref-$id"
done
```

Then ask Claude: *"Use the director skill to write Style DNA profiles for the
three references in deconstruct/ and a synthesis."* Already have the files?
Pass the paths instead of the URLs.
