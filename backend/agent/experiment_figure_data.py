import hashlib
import json

from agent import experiment_images

NAME = "read_experiment_figure_data"
TOOL = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "读取当前会话实际实验图的结构化绘图数据，纯文本模型也可调用。按实验ID/版本/完整图名定位，返回坐标轴、序列目录与指定序列数据；分页读取，不运行算法，不等于看过图片。旧图缺少保存的数据时明确返回不可用及方法证据，不从PNG猜数值。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["experiment_id", "figure_name"],
            "properties": {
                "experiment_id": {"type": "string"},
                "figure_name": {"type": "string"},
                "version": {"type": "integer", "minimum": 1},
                "axis_index": {"type": "integer", "minimum": 0, "default": 0},
                "series_index": {"type": "integer", "minimum": 0, "default": 0},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
        },
    },
}
PROMPT = (
    "read_experiment_figure_data读取本会话实验图真实绘图数据，不要求模型具备视觉；"
    "用实际experiment_id/version/figure_name，按返回轴/序列索引和next_offset分页。"
    "必须说明数据是否截断/不可用；读取结构化数据不等于看过图片，不能编造未保存的点或视觉细节。"
)


def read(root, owner, session, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("图形数据参数必须是对象。")
    if set(arguments) - TOOL["function"]["parameters"]["properties"].keys():
        raise ValueError("图形数据请求包含不支持的字段。")
    if "version" in arguments and (
        type(arguments["version"]) is not int or arguments["version"] < 1
    ):
        raise ValueError("version 必须是正整数。")
    indices = {}
    for key, default in (("axis_index", 0), ("series_index", 0), ("offset", 0), ("limit", 50)):
        value = arguments.get(key, default)
        if (
            type(value) is not int
            or value < (1 if key == "limit" else 0)
            or (key == "limit" and value > 200)
        ):
            raise ValueError(f"{key} 超出可用范围。")
        indices[key] = value
    version, figure, target = experiment_images.resolve(root, owner, session, arguments)
    evidence = {
        "experiment_id": arguments["experiment_id"],
        "version": version["version"],
        "figure_name": figure["name"],
        "image_attached": False,
        **experiment_images.result_evidence(version["result"], figure),
    }
    path = target.with_name(target.name + ".data.json")
    if not path.is_file():
        return {
            **evidence,
            "status": "unavailable",
            "message": "旧图没有保存结构化绘图数据；仅提供对应方法结果，不从像素恢复或重跑。",
        }
    if (
        not path.resolve().is_relative_to(target.parent.resolve())
        or path.is_symlink()
        or path.stat().st_size > 4_000_000
    ):
        raise ValueError("图形数据路径或体积无效。")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        data.get("schema") != 1
        or data.get("figure_name") != figure["name"]
        or data.get("image_sha256") != hashlib.sha256(target.read_bytes()).hexdigest()
    ):
        raise ValueError("图形数据与当前图像不匹配，不能作为本版本证据。")
    axes = data["axes"]
    if indices["axis_index"] >= len(axes):
        raise ValueError("axis_index 不存在，请按轴目录选择。")
    axis = axes[indices["axis_index"]]
    series = axis["series"]
    overview = [{key: value for key, value in item.items() if key != "data"} for item in series]
    if not series:
        return {
            **evidence,
            "status": "unavailable",
            "axis": axis,
            "message": "该轴无支持的数值序列；不从文本或像素推断。",
        }
    if indices["series_index"] >= len(series):
        raise ValueError("series_index 不存在，请按序列目录选择。")
    selected = series[indices["series_index"]]
    offset, limit = indices["offset"], indices["limit"]
    if offset > len(selected["data"]):
        raise ValueError("offset 超过已保存的数据范围。")
    rows = selected["data"][offset : offset + limit]
    return {
        **evidence,
        "status": "available",
        "source": data["source"],
        "notes": data["notes"],
        "coordinate_system": "per_series_artist_coordinates; unrecorded transforms are unresolved",
        "axes_truncated": data["axes_truncated"],
        "axes": [
            {key: item[key] for key in ("index", "title", "x_label", "y_label")} for item in axes
        ],
        "axis": {key: value for key, value in axis.items() if key != "series"},
        "series_catalog": overview,
        "series": {**selected, "data": rows},
        "offset": offset,
        "next_offset": offset + len(rows) if offset + len(rows) < len(selected["data"]) else None,
    }
