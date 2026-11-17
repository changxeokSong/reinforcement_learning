"""색 입힌 알바트로스 메시를 몸통·날개·다리로 나눈다. Unity에서 부위별로 움직이게 하려는 것이다.

실행: python tools/split_bird.py <albatross_tex.obj> <출력 폴더>
메시 좌표: y 위, z 앞(부리 쪽), x 오른쪽. 부위마다 회전 중심(pivot)을 원점으로 옮겨 저장하고,
pivot 위치는 parts.json에 적는다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

src, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
m = trimesh.load(src, force="mesh", process=False)
c = m.triangles_center
x, y, z = c[:, 0], c[:, 1], c[:, 2]

parts = {
    "WingL": (x < -0.36) & (y > -0.25) & (y < 0.6),
    "WingR": (x > 0.36) & (y > -0.25) & (y < 0.6),
    "LegL": (y < -0.66) & (x < 0) & (z > -0.3),
    "LegR": (y < -0.66) & (x >= 0) & (z > -0.3),
}
pivots = {"WingL": [-0.34, 0.33, 0.0], "WingR": [0.34, 0.33, 0.0],
          "LegL": [-0.15, -0.64, 0.12], "LegR": [0.15, -0.64, 0.12]}
taken = np.zeros(len(c), dtype=bool)
info = {}
for name, sel in parts.items():
    sel = sel & ~taken
    taken |= sel
    sub = m.submesh([np.nonzero(sel)[0]], append=True)
    sub.apply_translation(-np.array(pivots[name]))
    sub.export(out / f"{name}.obj")
    info[name] = {"pivot": pivots[name], "faces": int(sel.sum())}
body = m.submesh([np.nonzero(~taken)[0]], append=True)
body.export(out / "Body.obj")
info["Body"] = {"pivot": [0, 0, 0], "faces": int((~taken).sum())}
(out / "parts.json").write_text(json.dumps(info, indent=2))
print(info)
