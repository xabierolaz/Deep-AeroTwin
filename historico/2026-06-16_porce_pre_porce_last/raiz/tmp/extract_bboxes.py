import json
from pathlib import Path
RUN = Path(r"D:\Deep-AeroTwin-UE57-Test\pipeline\logs\zero_trust\20260612_233504")
# clip = original frames 5600..5980 step2 -> clip index = (frame-5600)//2
out = {}
for l in (RUN / "vision/events.jsonl").read_text(errors="ignore").splitlines():
    try:
        e = json.loads(l)
    except Exception:
        continue
    if e.get("kind") != "vision_frame":
        continue
    f = int(e.get("frame", -1))
    if not (5600 <= f <= 5980):
        continue
    og = e.get("outgoing")
    if not isinstance(og, list):
        continue
    boxes = []
    for o in og:
        if isinstance(o, dict) and o.get("bbox"):
            b = o["bbox"]
            boxes.append({
                "type": str(o.get("type", "")).lower(),
                "conf": round(float(o.get("confidence", 0)), 3),
                "x1": float(b["x1"]), "y1": float(b["y1"]),
                "x2": float(b["x2"]), "y2": float(b["y2"]),
            })
    out[(f - 5600) // 2] = boxes
Path(r"D:\Deep-AeroTwin-UE57-Test\tmp\clip_bboxes.json").write_text(json.dumps(out))
print("frames with boxes:", sum(1 for v in out.values() if v), "of", len(out))
# class tally
from collections import Counter
c = Counter()
for v in out.values():
    for o in v:
        c[o["type"]] += 1
print(dict(c))
