# external sanity check (exploratory, post-hoc)
# Probe remote zip central directory via HTTP Range requests (no full download).
import requests, struct, sys

URL = "https://huggingface.co/datasets/kianzohoury/shapenetcore/resolve/main/archive.zip"

def get_range(start, end):
    r = requests.get(URL, headers={"Range": f"bytes={start}-{end}"}, timeout=60)
    r.raise_for_status()
    return r.content

# total size from HEAD
h = requests.head(URL, allow_redirects=True, timeout=30)
size = int(h.headers.get("Content-Length", 0))
print("total size:", size)

tail = get_range(max(0, size - 2_000_000), size - 1)
# find EOCD
idx = tail.rfind(b"PK\x05\x06")
if idx < 0:
    print("EOCD not found in last 2MB"); sys.exit(1)
eocd = tail[idx:idx+22]
cd_size, cd_offset = struct.unpack("<II", eocd[12:20])
total_entries = struct.unpack("<H", eocd[10:12])[0]
print("entries:", total_entries, "cd_size:", cd_size, "cd_offset:", cd_offset)
cd = get_range(cd_offset, min(size - 1, cd_offset + cd_size - 1))
names = []
pos = 0
while pos < len(cd) - 4 and len(names) < total_entries:
    sig = cd[pos:pos+4]
    if sig != b"PK\x01\x02":
        break
    (nlen,) = struct.unpack("<H", cd[pos+28:pos+30])
    (elen,) = struct.unpack("<H", cd[pos+30:pos+32])
    (clen,) = struct.unpack("<H", cd[pos+32:pos+34])
    name = cd[pos+46:pos+46+nlen].decode("utf-8", "replace")
    names.append(name)
    pos += 46 + nlen + elen + clen
print("parsed names:", len(names))
import collections
roots = collections.Counter(n.split("/")[0] for n in names)
print("roots:", dict(roots))
# show category distribution if shapenet-like
cats = collections.Counter()
for n in names:
    parts = n.split("/")
    for p in parts:
        if p.isdigit() and len(p) == 8:
            cats[p] += 1
            break
for c, k in sorted(cats.items()):
    print("category", c, "entries:", k)
