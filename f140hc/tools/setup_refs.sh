#!/usr/bin/env bash
# Rebuild the working environment for the F140HC project in a fresh session.
#   bash f140hc/tools/setup_refs.sh [WORKDIR]        (default WORKDIR: ./f140_work, git-ignored)
# Creates:
#   WORKDIR/bpyenv   Python + bpy 5.2.3 (headless Blender) + opencv   -> build/render/fit scripts
#   WORKDIR/cvenv    Python + opencv + scipy + numpy + pillow         -> measurement scripts
#   WORKDIR/refs/amalgam/NN.jpg   the 23 Amalgam 1:4 product photos (01..23, order as listed)
#   WORKDIR/refs/hdri/*.hdr       CC0 studio HDRIs from Poly Haven
#   WORKDIR/refs/video/           EMPTY: the reveal video must be uploaded by the user (see HANDOVER.md)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
W="${1:-$PWD/f140_work}"
mkdir -p "$W/refs/amalgam" "$W/refs/hdri" "$W/refs/video"
[ -d "$W/bpyenv" ] || python3 -m venv "$W/bpyenv"
"$W/bpyenv/bin/pip" install -q bpy==5.2.3 opencv-python-headless
[ -d "$W/cvenv" ] || python3 -m venv "$W/cvenv"
"$W/cvenv/bin/pip" install -q opencv-python-headless numpy scipy pillow
python3 - "$HERE/../reference_data/amalgam_product.json" "$W/refs/amalgam" <<'PY'
import json, sys, urllib.request
d = json.load(open(sys.argv[1]))["product"]
for i, im in enumerate(d["images"], 1):
    url = im["src"].split("?")[0] + "?width=1800"
    out = "%s/%02d.jpg" % (sys.argv[2], i)
    urllib.request.urlretrieve(url, out); print(out)
PY
for n in studio_small_08 studio_small_09 photo_studio_01; do
  curl -sS --max-time 120 -o "$W/refs/hdri/${n}_2k.hdr" "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/${n}_2k.hdr"
done
echo "done. export F140_REFS=$W/refs ; F140_HDRI=$W/refs/hdri/studio_small_08_2k.hdr"
echo "video frames: ask the user to upload the reveal video, then:"
echo "  for t in 11.4 21.4; do ffmpeg -v error -ss \$t -i VIDEO.mp4 -frames:v 1 -q:v 2 $W/refs/video/f_\$(printf %05.1f \$t).jpg; done"
