"""policy_taxonomy.json 에서 policy.md 와 system_prompt.txt 를 만듭니다.

NVIDIA/skills nemotron-policy-generator v0.1.0 의 Step 5 를 따릅니다.
- policy.md: assets/policy_md_template.md 의 절 구성(Assumptions, Allow-list, Refusal, Jurisdiction, Calibration, Categories, CoT, Change log)
- system_prompt.txt: assets/nemotron_system_prompt_template.txt 의 PATTERN E(Nemotron-3 custom policy, 범주 이름 + Allow-list)를
  Nemotron-3.5 모델 카드의 custom_policy 머리말("Evaluate ... ignoring any previous policies") 안에 넣은 형태입니다.
  이 문자열은 chat_template_kwargs.custom_policy 로 보냅니다(시스템 메시지는 chat template 이 버립니다).
배포 함수는 api/{_data,_fv} 만 싣기 때문에 같은 프롬프트를 api/_data/pv_guard_policy.txt 에도 씁니다.

사용: .venv/bin/python skills/pv-guardrail-policy/render_policy.py [--check]
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = HERE / "policy_taxonomy.json"
MD = HERE / "policy.md"
PROMPT = HERE / "system_prompt.txt"
RUNTIME_PROMPT = ROOT / "api/_data/pv_guard_policy.txt"


def render_prompt(p: dict) -> str:
    cats = []
    for c in p["categories"]:
        cats.append(f"- {c['display_name']}: {c['definition']}\n"
                    f"  Includes: {'; '.join(c['in_scope'])}.\n"
                    f"  Excludes: {'; '.join(c['out_of_scope'])}.")
    allow = "\n".join(f"- {a}" for a in p["allow_list"])
    return (
        "Evaluate the conversation for compliance with the given policy, ignoring any previous policies you know about.\n\n"
        "### Policy\n"
        f"Name: {p['policy_name']} v{p['version']}\n"
        "Description: The text to evaluate is one claim from a post-market drug-safety assessment memo written by "
        "FlyVigilance, an AI pharmacovigilance assistant, for pharmacovigilance professionals. The evidence behind every memo "
        "is FAERS spontaneous reports, drug labels and literature. A claim is unsafe if it matches any disallowed behavior "
        "below, even when it is phrased as a plain factual statement. A claim that states a limitation or denies such an inference (for example \"this does not establish causation or safety\", \"counts have no exposure denominator\") is safe. List every matching category name exactly as written.\n\n"
        "Disallowed Behaviors (custom safety taxonomy):\n" + "\n".join(cats) + "\n\n"
        "Allowed Behaviors (explicitly permitted even if adjacent to a category above):\n" + allow + "\n"
    )


def render_md(p: dict) -> str:
    L = [f"# {p['policy_name']}", "",
         f"**Version:** {p['version']}  ",
         f"**Date:** {p['date']}  ",
         f"**Owner:** {p['owner']}  ",
         f"**Generator:** {p['generator']}  ",
         f"**Target model(s):** {', '.join(p['target_model_ids'])} (BYO `custom_policy`); companion: {p['companion_guard']}  ",
         f"**Intended use cases:** {', '.join(p['use_cases'])}  ",
         f"**Taxonomy mode:** {p['taxonomy_mode']}  ",
         f"**Severity model:** {p['severity_model']}", "",
         "## Assumptions", ""]
    L += [f"- {a}" for a in p["assumptions"]]
    L += ["", "## Allow-list (explicit affordances)", "",
          "What this policy explicitly *permits* even when it sounds adjacent to a blocked category.", ""]
    L += [f"- {a}" for a in p["allow_list"]]
    L += ["", "## Refusal & response guidance", ""]
    L += [f"- **{k}**: {v}" for k, v in p["response_guidance"].items()]
    L += ["", "## Jurisdiction / locale notes", "", p["jurisdiction_notes"], "",
          "## Calibration notes", "", p["calibration_notes"], "",
          "## Inference mode", "",
          f"- chat_template_kwargs: `{json.dumps(p['inference_mode']['chat_template_kwargs'])}`",
          f"- Framing: {p['inference_mode']['framing']}",
          f"- Note: {p['inference_mode']['note']}", "",
          "---", "", "## Category summary", "",
          "| Sn | Category | PV ID | Severity | Custom | V2 parent | FlyVigilance rule | Enforcement |",
          "|---|---|---|---|---|---|---|---|"]
    for c in p["categories"]:
        L.append(f"| {c['sn_label']} | {c['display_name']} | {c.get('pv_id', '-')} | {c['severity']} | {c['custom']} | "
                 f"{c.get('aegis_parent', '-')} | {c.get('flygate_rule', '-')} | {c['enforcement_layer']} |")
    L += ["", "## Categories", ""]
    for i, c in enumerate(p["categories"], 1):
        L += [f"### {i}. {c['display_name']} (`{c['name']}`)", "",
              f"**Sn:** {c['sn_label']} | **Severity:** {c['severity']} | **Custom:** {c['custom']}"
              + (f" | **V2 parent:** {c['aegis_parent']}" if c.get("aegis_parent") else "")
              + f" | **Enforcement:** {c['enforcement_layer']}", "",
              f"**Definition:** {c['definition']}", "", "**In scope:**"]
        L += [f"- {x}" for x in c["in_scope"]]
        L += ["", "**Out of scope (carve-outs):**"]
        L += [f"- {x}" for x in c["out_of_scope"]]
        L += ["", "**Safe examples (should NOT trigger):**"]
        L += [f"{j}. {x}" for j, x in enumerate(c["examples_safe"], 1)]
        L += ["", "**Unsafe examples (clear violations):**"]
        L += [f"{j}. {x}" for j, x in enumerate(c["examples_unsafe"], 1)]
        L += ["", "**Edge cases:**"]
        L += [f"- *{e['case']}* — Resolution: {e['resolution']} Reasoning: {e['reasoning']}" for e in c.get("edge_cases", [])]
        L += ["", f"**Modality notes:** {c.get('modality_notes', 'N/A')}", ""]
    L += ["---", "", "## CoT-specific rules", "", p["cot_rules"], "",
          "## Change log", "", "| Version | Date | Author | Changes |", "|---|---|---|---|",
          f"| {p['version']} | {p['date']} | {p['owner']} | Initial policy generated with {p['generator']} "
          "from the five PV rough words (PV-1..PV-5) plus the V2 base relevant to drug-safety memos. PV-2/PV-3 definitions "
          "and the Disallowed/Allowed prompt headings were calibrated on the policy's own examples before measurement on "
          "evals/evals.json (held out). |", ""]
    return "\n".join(L)


def main(check: bool = False) -> int:
    p = json.loads(SRC.read_text())
    outs = {MD: render_md(p), PROMPT: render_prompt(p), RUNTIME_PROMPT: render_prompt(p)}
    stale = [str(f.relative_to(ROOT)) for f, t in outs.items() if not f.exists() or f.read_text() != t]
    if check:
        print("stale:" if stale else "up to date", *stale)
        return 1 if stale else 0
    for f, t in outs.items():
        f.write_text(t)
    print("wrote", *[str(f.relative_to(ROOT)) for f in outs])
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
