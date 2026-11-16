"""Bounded evidence selection and local near-duplicate guards; no model calls."""

import re
import unicodedata
from difflib import SequenceMatcher

from agent.study_graph import fail
from config import (
    SELF_CHECK_QUALITY_MAX_CHARS as MAX_CHARS,
)
from config import (
    SELF_CHECK_QUALITY_MAX_EVIDENCE as MAX_EVIDENCE,
)


def normalize(text):
    text = unicodedata.normalize("NFKC", str(text)).lower()
    for old, new in [
        ("出现的次数", "出现次数"),
        ("出现数量", "出现次数"),
        ("观测次数", "出现次数"),
        ("不能说明", "不能证明"),
        ("不可以", "不能"),
        ("训练数据", "训练集"),
        ("测试数据", "测试集"),
    ]:
        text = text.replace(old, new)
    text = re.sub(r"教学示例|请判断|判断下列说法|下列说法|是否正确|请选择|请简述|请说明", "", text)
    text = re.sub(r"\d+(?:\.\d+)?", "数值", text)
    return re.sub(r"[^a-z\u4e00-\u9fff]+", "", text)


def similarity(left, right):
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0
    if a == b:
        return 1

    def pairs(value):
        return {value[i : i + 2] for i in range(len(value) - 1)}

    aa, bb = pairs(a), pairs(b)
    dice = 2 * len(aa & bb) / max(1, len(aa) + len(bb))
    return max(dice, SequenceMatcher(None, a, b, autojunk=False).ratio())


def duplicate(left, right):
    if similarity(left["prompt"], right["prompt"]) >= 0.82:
        return True

    # Negating a statement or asking for the same fact in a different question
    # type does not turn it into a new learning objective.
    def strip(value):
        return re.sub(r"是否|能够|可以|不能|必须|应该|应当|无需|不", "", value)

    return similarity(strip(left["prompt"]), strip(right["prompt"])) >= 0.9


def check(questions, previous=()):
    accepted = []
    for question in questions:
        for old in [*previous, *accepted]:
            if duplicate(question, old):
                fail(
                    f"{question['id']}与同卷或近期试卷题目过于相近；请更换考察情境或推理任务，不能只换词、换数字或正反说法。",
                    "duplicate_question",
                )
        accepted.append(question)


def material(frozen, previous=()):
    """Keep the complete frozen source on disk, send distributed bounded excerpts."""
    points = frozen["blueprint"]["points"]
    words = set(
        re.findall(
            r"[A-Za-z_]{3,}|[\u4e00-\u9fff]{2,4}",
            frozen["blueprint"]["label"] + " " + " ".join(p["expected"] for p in points),
        )
    )

    def rank(item):
        return sum(word in item["text"] for word in words) + 3 * (
            frozen["blueprint"]["method_id"] in item["text"]
        )

    groups = {
        turn: [e for e in frozen["evidence"] if e["turn"] == turn]
        for turn in frozen["candidate_turns"]
    }
    ranked = sorted(
        groups, key=lambda t: max((rank(e) for e in groups[t]), default=0), reverse=True
    )
    all_turns = sorted(groups)
    # Relevant early teaching remains eligible; never replace the history by a
    # last-six-turn window. Every selected turn gets a question and an answer.
    turns = list(dict.fromkeys(ranked[:3] + all_turns[:: max(1, len(all_turns) // 3)][:3]))[:6]
    chosen = []
    for turn in turns:
        for kind in ("user/message", "assistant/message"):
            candidates = [e for e in groups[turn] if e["kind"] == kind]
            if candidates:
                chosen.append(max(candidates, key=rank))
    experiments = {}
    for item in sorted(frozen["evidence"], key=rank, reverse=True):
        if item["kind"] == "tool/result" and item.get("experiment_id"):
            experiments.setdefault((item["experiment_id"], item.get("version")), []).append(item)

    # Prefer concrete metrics and table rows to the large tool envelope.
    def experiment_rank(item):
        return rank(item) + sum(
            3 for word in ('"tables"', '"rows"', '"metrics"', '"params"') if word in item["text"]
        )

    experiments = {
        key: sorted(group, key=experiment_rank, reverse=True) for key, group in experiments.items()
    }
    for index in range(4):
        for group in experiments.values():
            if index < len(group) and len(chosen) < MAX_EVIDENCE:
                chosen.append(group[index])
    # Small lessons need no padding. Large ones can use spare high-value spans.
    for item in sorted(frozen["evidence"], key=rank, reverse=True):
        if len(chosen) >= MAX_EVIDENCE:
            break
        if item not in chosen and item["kind"] == "assistant/message":
            chosen.append(item)
    evidence = []
    remaining = MAX_CHARS
    for item in chosen:
        if remaining < 80:
            break
        text = item["text"][: min(500, remaining)]
        evidence.append(
            {
                k: item[k]
                for k in ("id", "turn", "kind", "experiment_id", "version", "evidence_quality")
                if k in item
            }
            | {"text": text}
        )
        remaining -= len(text)
    candidates = sorted({e["turn"] for e in evidence})
    sample = {k: frozen[k] for k in ("blueprint", "scope_note", "selection_partial")}
    sample.update(
        candidate_turns=candidates,
        evidence=evidence,
        prior_questions=[{**q, "prompt": q["prompt"][:350]} for q in previous],
        selection_partial=frozen["selection_partial"] or len(evidence) < len(frozen["evidence"]),
        scope_note=f"已冻结全部{frozen['candidate_count']}轮候选交流；出题输入选取{len(evidence)}段原文，只考这些片段能证明已学过的内容。",
    )
    # Source URLs are audit metadata on disk, not extra knowledge to improvise.
    sample["blueprint"] = {
        k: sample["blueprint"][k] for k in ("method_id", "label", "version", "variant", "summary", "points")
        if k in sample["blueprint"]
    }
    return sample
