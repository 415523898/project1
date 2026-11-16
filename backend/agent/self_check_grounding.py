"""Server-owned learning/experiment contexts; model picks one opaque context ID.

Context validation follows the runtime-context pattern used by Pydantic AI:
https://github.com/pydantic/pydantic-ai/blob/main/docs/output.md
No third-party implementation is copied here.
"""

import copy
from collections import defaultdict

from agent.study_graph import fail


def contexts(anchors):
    learning = defaultdict(list)
    experiments = defaultdict(list)
    for alias, item in anchors.items():
        if item["kind"] in ("user/message", "assistant/message"):
            learning[item["turn"]].append(alias)
        if (
            item.get("experiment_id")
            and type(item.get("version")) is int
            and item.get("evidence_quality") == "snapshot"
            and item["kind"] == "tool/result"
        ):
            experiments[(item["experiment_id"], item["version"])].append(alias)
    result = []
    for turn, refs in sorted(learning.items()):
        result.append({"id": f"c{len(result) + 1}", "kind": "learning", "evidence_ids": refs[:6]})
    for (identifier, version), refs in sorted(experiments.items()):
        turns = {anchors[ref]["turn"] for ref in refs}
        companions = [ref for turn in sorted(turns) for ref in learning[turn]]
        result.append(
            {
                "id": f"c{len(result) + 1}",
                "kind": "experiment",
                "evidence_ids": (refs[:4] + companions[:2])[:6],
                "experiment_id": identifier,
                "version": version,
            }
        )
    return result


def bind(question, available, anchors):
    """The ID binds source text, basis and fixed version as a single choice."""
    question = copy.deepcopy(question)
    identifier = str(question.get("context_id", "")).strip().lower()
    context = next((c for c in available if c["id"] == identifier), None)
    if not context:
        fail("请选择本次提供的学习或实验情境编号。", "invalid_grounding")
    if question.get("basis_kind") not in (None, context["kind"]):
        fail("题目依据类型与所选情境不一致；实验题必须选择实验快照情境。", "invalid_grounding")
    refs = context["evidence_ids"]
    if context["kind"] == "experiment" and not any(
        anchors[r].get("experiment_id") == context["experiment_id"]
        and anchors[r].get("version") == context["version"]
        and anchors[r].get("evidence_quality") == "snapshot"
        for r in refs
    ):
        fail("所选实验情境缺少固定版本快照。", "invalid_grounding")
    kind = (
        "example"
        if context["kind"] == "learning" and "教学示例" in question.get("prompt", "")
        else context["kind"]
    )
    question.update(basis_kind=kind, evidence_ids=list(refs))
    return question
