"""Learning direction metadata reported by the main conversation, without another model."""

from engine import catalog

NAME = "report_learning_direction"
PROMPT = """学习方向由本轮主对话判断，不另行请求识别模型。
每个用户轮次至多调用一次 report_learning_direction，记录最新用户的学习意图后继续正常回答。
明确要学习某个方法或有足够具体的问题时用 learn，method_id 必须是工具枚举中的真实标识，evidence 逐字摘取最新用户问题。
描述笼统、问候或证据不足时用 unsure，正常询问希望学习的方法或解决的问题，不强推卡片。
已绑定时，前置知识、方法比较、举例、实验及跨方法讨论可用 related；只有用户明确开始学习另一个方法才用 learn。
不能根据你自己提及的方法推断用户转向。方法不确定时先查方法库或追问，不猜标识。
该工具仅记录界面建议，不执行实验、不创建卡片、不绑定或换绑会话。
用户要求生成或绑定卡片时，报告明确方向后指引点击右侧“让AI匹配方法并生成学习卡片”；不能声称已生成、已绑定或已经弹出确认框。
方法名称与 ID 以工具枚举及方法库为准，例如随机森林是 ml.random_forest，ml.trees 是决策树。最终答复仍用正常正文输出。"""
TOOL = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "记录主对话判断的学习方向，供顶部绑定或新会话建议使用；不自动绑定。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "intent": {"type": "string", "enum": ["learn", "related", "unsure"]},
                "method_id": {"type": ["string", "null"], "enum": [None, *sorted(catalog.BY_ID)]},
                "evidence": {
                    "type": "string",
                    "description": "最新用户问题中的原文；不确定时留空。",
                },
            },
            "required": ["intent", "method_id", "evidence"],
        },
    },
}


def validate(value, question):
    if not isinstance(value, dict) or set(value) != {"intent", "method_id", "evidence"}:
        raise ValueError("学习方向参数无效。")
    intent, method, evidence = value["intent"], value["method_id"], value["evidence"]
    if intent not in ("learn", "related", "unsure") or not isinstance(evidence, str):
        raise ValueError("学习意图或原文依据无效。")
    if method is not None and (not isinstance(method, str) or method not in catalog.BY_ID):
        raise ValueError("请使用方法库中的真实方法标识。")
    evidence = evidence.strip()
    if intent == "learn" and (not method or len(evidence) < 2 or evidence not in question):
        raise ValueError("明确学习方向必须引用最新用户问题的原文依据。")
    return {"intent": intent, "method_id": method, "evidence": evidence}
