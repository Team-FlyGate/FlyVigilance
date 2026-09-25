"""skills/*/SKILL.md 를 대시보드용 JSON 으로 묶는다."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
out = []
for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
    text = p.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    front, body = m.group(1), m.group(2)
    get = lambda k: (re.search(rf"^{k}:\s*(.+)$", front, re.M) or [None, ""])[1].strip()
    meta = dict(re.findall(r"^\s{2}(\w+):\s*(.+)$", front, re.M))
    out.append({"name": get("name"), "description": get("description"), "license": get("license"),
                "layer": meta.get("layer", ""), "model": meta.get("model", ""), "path": str(p.relative_to(ROOT)), "body": body.strip()})
(ROOT / "web/public/data/skills.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(len(out), "skills")
