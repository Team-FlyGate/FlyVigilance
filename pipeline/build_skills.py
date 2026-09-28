"""skills/*/SKILL.md 를 대시보드용 JSON 으로 묶습니다.

프런트매터는 NVIDIA Agent Skills 규격(name, title, version, description, license, compatibility, metadata)을 따릅니다.
Skills.tsx 가 쓰는 기존 필드(name, description, license, layer, model, path, body)는 그대로 두고,
title, version, compatibility, domain, tags, based_on, skill_card, evals 를 더합니다.
"""
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = "https://github.com/Team-FlyGate/Project-FlyGate/blob/main"


def s(v) -> str:
    return "" if v is None else str(v).strip()


out = []
for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
    text = p.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    front, body = yaml.safe_load(m.group(1)) or {}, m.group(2)
    meta = front.get("metadata") or {}
    d = p.parent
    card = d / "skill-card.md"
    evals = d / "evals" / "evals.json"
    n_evals = len(json.loads(evals.read_text())) if evals.exists() else 0
    rel_card = str(card.relative_to(ROOT)) if card.exists() else ""
    out.append({
        "name": s(front.get("name")), "title": s(front.get("title")),
        "version": s(front.get("version") or meta.get("version")),
        "description": s(front.get("description")), "license": s(front.get("license")),
        "compatibility": s(front.get("compatibility")),
        "layer": s(meta.get("layer")), "model": s(meta.get("model")), "domain": s(meta.get("domain")),
        "tags": [str(t) for t in (meta.get("tags") or [])], "based_on": s(meta.get("based_on")),
        "path": str(p.relative_to(ROOT)), "body": body.strip(),
        "skill_card": rel_card, "skill_card_url": f"{REPO}/{rel_card}" if rel_card else "",
        "skill_card_md": card.read_text().strip() if card.exists() else "",
        "evals": n_evals,
    })
(ROOT / "web/public/data/skills.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(len(out), "skills,", sum(1 for x in out if x["skill_card"]), "skill cards,", sum(1 for x in out if x["evals"]), "with evals")
