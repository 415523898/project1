"""Create (or refresh) a study card from a conversation without binding a method."""

import json
import uuid

from agent import eventlog, learning_exploration, provider, study_model, study_store as store

SYSTEM = """把这段会话整理成一张学习卡片，不要求对应方法库里的方法。
卡片面向复习：标题点明主题或数据对象，摘要写清本段到底学了什么，正文保留关键结论、步骤和注意事项。
标题不超过 24 字符；摘要不超过 160 字符；正文不超过 3000 字符。不要编造会话中没有的数值或结论。
只输出 JSON：{"title":"...","summary":"...","body":"..."}。"""


def _rounds(root, owner, session):
    record = eventlog.Store(root, owner).get(session)
    return learning_exploration.completed_rounds(record["events"]), record


def _clean(value, limit):
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:limit]


def _event_ref(turn):
    value = str(turn.get("event_id") or "")
    return value if value.startswith("seq:") else "event:" + value


def _source(session, rounds):
    refs = [_event_ref(turn) for turn in rounds]
    return {
        "session_id": session,
        "event_refs": refs,
        "turn_start_seq": max(0, int(rounds[0].get("start_seq") or 0)),
        "cutoff_seq": max(0, int(rounds[-1].get("seq") or 0)),
        "precision": "legacy" if any(ref.startswith("seq:") for ref in refs) else "event",
    }


def topic_card(root, owner, session):
    """The automatic, method-less card sourced from this conversation, if any."""
    with store.connection(root, owner) as db:
        sources = [
            json.loads(raw)
            for (raw,) in db.execute("SELECT payload FROM sources WHERE session_id=?", (session,))
        ]
        for source in sources:
            row = db.execute(
                "SELECT payload FROM cards WHERE card_id=?", (source["card_id"],)
            ).fetchone()
            if not row:
                continue
            card = json.loads(row[0])
            if not card.get("method_ids") and card.get("created_by") == "user":
                return card
    return None


def _create(root, owner, session, rounds, title, summary, body):
    value = store.workspace(root, owner)
    request = {
        "schema_version": 2,
        "operation_id": "topic_" + uuid.uuid4().hex,
        "base_graph_revision": value["graph_revision"],
        "base_layout_revision": value["layout_revision"],
        "operations": [
            {
                "op": "create_card",
                "client_ref": "topic_card",
                "values": {
                    "title": title,
                    "summary": summary,
                    "body": body,
                    "type": "conversation",
                    "method_ids": [],
                },
                "sources": [_source(session, rounds)],
            },
            {
                "op": "add_node",
                "card_id": "topic_card",
                "x": 40,
                "y": max((node["y"] for node in value["nodes"]), default=-192) + 288,
            },
        ],
    }
    result = store.apply_changes(root, owner, request)
    return result["id_map"]["topic_card"]


def _update(root, owner, card, title, summary, body):
    value = store.workspace(root, owner)
    request = {
        "schema_version": 2,
        "operation_id": "topic_" + uuid.uuid4().hex,
        "base_graph_revision": value["graph_revision"],
        "base_layout_revision": value["layout_revision"],
        "operations": [
            {
                "op": "update_card",
                "card_id": card["card_id"],
                "expected_revision": card["revision"],
                "changes": {"title": title, "summary": summary, "body": body},
            }
        ],
    }
    store.apply_changes(root, owner, request)
    return card["card_id"]


def _content(settings, record, rounds):
    sample = [
        {"question": turn["question"][:1500], "answer": turn["answer"][:5000]}
        for turn in rounds[-3:]
    ]
    target, key, model = settings
    request = {"model": model, "stream": False, **study_model.options(model, 2048)}
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {"title_hint": record.get("title") or "", "turns": sample},
                ensure_ascii=False,
            ),
        },
    ]
    reply = provider.call(target, key, {**request, "messages": messages})
    answer = provider.parse_message(reply)["answer"].strip()
    if answer.startswith("```") and answer.endswith("```"):
        answer = answer.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = answer.find("{"), answer.rfind("}")
    try:
        value = json.loads(answer[start : end + 1])
    except ValueError:
        raise ValueError("模型没有返回有效的卡片内容，请重试。") from None
    title = _clean(value.get("title"), 24)
    summary = _clean(value.get("summary"), 160)
    body = _clean(value.get("body"), 3000)
    if not title or not summary:
        raise ValueError("模型没有给出卡片标题或摘要，请重试。")
    return title, summary, body


def generate(root, owner, session, settings, update_existing=True):
    """Write the session card once, or refresh the one already written."""
    rounds, record = _rounds(root, owner, session)
    if not rounds:
        raise ValueError("请先完成至少一轮对话，再生成学习卡片。")
    existing = topic_card(root, owner, session)
    if existing and not update_existing:
        return None
    title, summary, body = _content(settings, record, rounds)
    # A manual click and the automatic pass can finish together; the second one
    # reuses the card written by the first instead of adding a duplicate.
    lock = learning_exploration.locks(
        learning_exploration.state_path(root, owner, session)
    )[1]
    if not lock.acquire(blocking=False):
        raise ValueError("正在生成这个会话的卡片，请稍候。")
    try:
        latest = topic_card(root, owner, session)
        if latest:
            if not update_existing:
                return None
            card_id = _update(root, owner, latest, title, summary, body)
            updated = True
        else:
            card_id = _create(root, owner, session, rounds, title, summary, body)
            updated = False
    finally:
        lock.release()
    return {
        "created": card_id,
        "updated": updated,
        "title": title,
        "summary": summary,
        "binding": None,
    }
