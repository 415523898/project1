import re
from functools import lru_cache

POLICY = """面向学习者的文字只使用方法中文名称、可见的操作和统计含义。
内部方法ID、私有函数/工具名、源码路径和本地模块入口只供工具调用与服务端关联，不能出现在教学正文、题目、选项、解析、评分要点或补学建议中。
代码示例使用 pandas、scipy、scikit-learn、statsmodels 等公开库，包含可独立运行的数据与导入；不要调用本应用私有模块。
不考查应用隐藏的默认参数、返回字段或内部调用方式。需要比较统计量时，明确给出统计口径和情境，再考查选择理由与结果含义。"""

PRIVATE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/](?:[A-Za-z0-9_\u4e00-\u9fff .-]+[\\/])+[^\s`<>\"，。；）]+|\bbackend[\\/](?:agent|engine|api|tools|utils)[\\/][^\s`<>\"，。；）]+)"
)
PRIVATE_CODE = re.compile(
    r"\b(?:from|import)\s+(?:backend|engine|agent|ml_tools|registry)\b|\b(?:engine\.params|params\.for_method|ml_tools\.\w+)"
)
TOOL_LABELS = {
    "run_ml_suite": "运行分析实验",
    "search_ml_methods": "检索分析方法",
    "inspect_datasets": "查看数据集",
    "view_experiment_image": "查看实验图像",
    "read_experiment_figure_data": "读取图表数据",
    "report_formula_learning": "公式学习意愿",
    "report_learning_direction": "学习目标确认",
    "extract_learning_units": "提取学习要点",
    "compose_learning_card": "整理学习卡片",
    "connect_learning_cards": "整理卡片关系",
    "prepare_self_check": "准备学习自测",
    "grade_self_check": "评价自测作答",
}
PRIVATE_TOOL = re.compile(r"\b(?:" + "|".join(TOOL_LABELS) + r")\b")
INTERNAL_TRIVIA = re.compile(
    r"代码入口|源码路径|本地接口|私有(?:接口|函数|模块)|默认(?:输出|返回|聚合函数)|(?:本项目|本应用|内部|接口).{0,12}(?:默认|参数名|返回字段|调用方式)"
    r"|当前.{0,6}实现.{0,16}(?:默认|参数|返回|输出|隐藏|调用|字段|分母)"
    r"|(?:未传入|不传入|未指定).{0,16}(?:默认|返回|输出)"
    r"|(?:后端|服务端).{0,10}(?:参数名|接口|函数|字段)"
)


@lru_cache(maxsize=1)
def methods():
    from engine.catalog import BY_ID

    names = {mid: item["label"] for mid, item in BY_ID.items()}
    pattern = re.compile(r"(?<![\w.])(?:" + "|".join(map(re.escape, names)) + r")(?![\w.])")
    return names, pattern


def private_content(text):
    return bool(
        methods()[1].search(text)
        or PRIVATE_PATH.search(text)
        or PRIVATE_CODE.search(text)
        or PRIVATE_TOOL.search(text)
    )


def inaccessible_question(question):
    texts = [question.get("prompt", ""), question.get("explanation", "")]
    texts += [option["text"] for option in question.get("options", [])]
    texts += [item["text"] for item in question.get("rubric", [])]
    return any(
        PRIVATE_PATH.search(item)
        or PRIVATE_CODE.search(item)
        or PRIVATE_TOOL.search(item)
        or INTERNAL_TRIVIA.search(item)
        for item in texts
    )


def learner_text(text):
    names, pattern = methods()
    text = re.sub(
        r"(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1",
        lambda match: (
            "> 此历史代码示例依赖应用内部功能。可继续询问使用公开 Python 库的独立示例。"
            if private_content(match[0])
            else match[0]
        ),
        text,
    )
    text = re.sub(r"代码入口\s*", "", text)
    text = PRIVATE_PATH.sub("应用内部实现", text)
    text = PRIVATE_CODE.sub("实验参数设置", text)
    text = PRIVATE_TOOL.sub(lambda match: TOOL_LABELS[match[0]], text)
    return pattern.sub(lambda match: names[match[0]], text)


def presentation(value, field=""):
    if isinstance(value, dict):
        return {key: presentation(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [presentation(item, field) for item in value]
    if isinstance(value, str) and field in {
        "prompt",
        "text",
        "title",
        "label",
        "explanation",
        "reason",
        "feedback",
        "advice",
        "quote",
        "lesson_quote",
        "scope_note",
        "summary",
        "missing_points",
        "uncovered_points",
        "error",
        "message",
    }:
        return learner_text(value)
    return value
