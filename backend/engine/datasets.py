from pathlib import Path

import numpy as np


class Unavailable(Exception):
    pass


def _pandas():
    try:
        import pandas as pd
    except ImportError as error:
        raise Unavailable("读取数据需要 pandas，请在 .venv 中安装后重试。") from error
    return pd


DATASETS = {
    "iris": {
        "file": "iris_training.csv",
        "kind": "iris_metadata",
        "task": "classification",
        "label": "Iris 鸢尾花（4 个测量特征，3 类）",
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
    },
    "wine": {
        "file": "wine_training.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "Wine 葡萄酒（13 个化学特征，3 类）",
        "target": "target",
        "drop": [],
    },
    "boston": {
        "file": "boston_housing.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Boston 房价（目标 medv）",
        "target": "medv",
        "drop": [],
        "column_metadata": {
            "medv": {
                "title": "自住房价值中位数",
                "unit": "1000 USD",
                "description": "原始数值单位为千美元，不是美元，也不是单套房成交价。",
                "source": "https://stat.ethz.ch/R-manual/R-devel/library/MASS/html/Boston.html",
            }
        },
    },
    "auto_mpg": {
        "file": "auto_mpg.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Auto MPG 汽车燃油经济性（目标 mpg，每加仑英里数，越高越省油）",
        "target": "mpg",
        "drop": [],
        "column_metadata": {
            "mpg": {
                "title": "燃油经济性",
                "unit": "mile/US gallon",
                "description": "每美制加仑燃油可行驶的英里数，mpg越高越省油；高mpg不是高油耗。预测mpg偏高表示高估燃油经济性、低估单位里程燃油消耗。",
                "higher_values_mean": "燃油经济性更高、更省油，单位里程燃油消耗更低。",
                "lower_values_mean": "燃油经济性更低、更费油，单位里程燃油消耗更高。",
                "source": "https://archive.ics.uci.edu/dataset/9/auto+mpg",
            }
        },
    },
    "real_estate": {
        "file": "real_estate.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Real Estate 房价估值（目标每坪单价，含距捷运距离）",
        "target": "price_per_unit_area",
        "drop": [],
        "column_metadata": {
            "price_per_unit_area": {
                "title": "房屋每坪单价",
                "unit": "10000 TWD/ping",
                "description": "原始单位为万新台币/坪，不是房屋总价，也不是每平方米单价。",
                "source": "https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set",
            }
        },
    },
    "concrete": {
        "file": "concrete.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Concrete 混凝土抗压强度（目标 compressive_strength，8 种配比特征）",
        "target": "compressive_strength",
        "drop": [],
        "column_metadata": {
            "compressive_strength": {
                "title": "混凝土抗压强度",
                "unit": "MPa",
                "description": "数值越大表示抗压强度越高；原单位为兆帕，不是混合物重量。",
                "source": "https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength",
            }
        },
    },
    "airfoil": {
        "file": "airfoil.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Airfoil 翼型自噪声（目标声压级 scaled_sound_pressure）",
        "target": "scaled_sound_pressure",
        "drop": [],
        "column_metadata": {
            "scaled_sound_pressure": {
                "title": "缩放声压级",
                "unit": "dB",
                "description": "声压级使用分贝这一对数尺度，不能把分贝差直接当作声压或声能的百分比变化。",
                "source": "https://archive.ics.uci.edu/dataset/291/airfoil+self+noise",
            }
        },
    },
    "breast_cancer": {
        "file": "breast_cancer.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "Breast Cancer Wisconsin 乳腺癌诊断（30 个细胞核特征，恶性/良性）",
        "target": "diagnosis",
        "drop": [],
        "class_names": ["良性", "恶性"],
    },
    "pima_diabetes": {
        "file": "pima_diabetes.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "Pima Indians Diabetes 皮马印第安人糖尿病（8 项生理指标）",
        "target": "outcome",
        "drop": [],
        "class_names": ["未患病", "患病"],
    },
    "titanic": {
        "file": "titanic.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "Titanic 乘客生存（舱位、性别、年龄、票价等，保留 Age 缺失值）",
        "target": "survived",
        "drop": [],
        "class_names": ["遇难", "生还"],
    },
    "wine_quality_red": {
        "file": "wine_quality_red.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Wine Quality 红酒（目标 quality 3–9，按有序数值处理）",
        "target": "quality",
        "drop": [],
    },
    "wine_quality_white": {
        "file": "wine_quality_white.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Wine Quality 白酒（目标 quality 3–9，按有序数值处理）",
        "target": "quality",
        "drop": [],
    },
    "air_passengers": {
        "file": "air_passengers.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "AirPassengers 国际航空月度乘客数（1949–1960，144 个月）",
        "target": "passengers",
        "drop": [],
        "time_column": "date",
        "column_metadata": {
            "passengers": {
                "title": "每月国际航空旅客总数",
                "unit": "1000 persons",
                "description": "原始数值单位为千人，例如112表示11.2万人，不是112人。",
                "source": "https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/AirPassengers.html",
            }
        },
    },
    "souvenir_sales": {
        "file": "souvenir_sales.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Souvenir 纪念品店月度销售额（1987–1993，84 个月，可做季节性分解与指数平滑）",
        "target": "sales",
        "drop": [],
        "time_column": "date",
    },
    "nile": {
        "file": "nile.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Nile 尼罗河年径流量（1871–1970，100 年）",
        "target": "value",
        "drop": [],
        "time_column": "time",
    },
    "sunspots": {
        "file": "sunspots.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Sunspots 太阳黑子月度均值（1749–1984，2820 个月，11 年周期）",
        "target": "value",
        "drop": [],
        "time_column": "time",
    },
    "ecommerce_reviews": {
        "file": "ecommerce_reviews.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "外卖电商中文评论情感（11987 条，好评/差评，含评论长度与标点特征）",
        "target": "label",
        "drop": ["review", "review_id"],
        "text_column": "review",
        "class_names": ["差评", "好评"],
    },
    "consumer_survey": {
        "file": "consumer_survey.csv",
        "kind": "tabular",
        "task": "classification",
        "label": "Somerville 消费者幸福感问卷（6 个 1–7 分李克特量表题项，目标 d 为总体评价）",
        "target": "d",
        "drop": [],
        "class_names": ["总体不满意", "总体满意"],
    },
    "nps_survey": {
        "file": "nps_survey.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "电信客户 NPS 问卷（目标 recommend_score 0–10 推荐意愿）",
        "target": "recommend_score",
        "drop": [
            "survey_id",
            "survey_date",
            "customer_id",
            "operator",
            "survey_type",
            "nps_category",
            "city",
            "customer_segment",
            "channel",
        ],
        "time_column": "survey_date",
        "group_column": "customer_id",
        "limit": 20000,
    },
    "grunfeld": {
        "file": "grunfeld.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "Grunfeld 企业投资面板（10 家企业 × 20 年，目标 invest）",
        "target": "invest",
        "drop": ["firm", "year"],
        "time_column": "year",
        "group_column": "firm",
    },
    "cps_wages": {
        "file": "cps_wages.csv",
        "kind": "tabular",
        "task": "regression",
        "label": "CPS 1985 工资数据（目标 wage，含教育年限与工作经验）",
        "target": "wage",
        "drop": [],
        "column_metadata": {
            "wage": {
                "title": "每小时工资",
                "unit": "USD/hour",
                "description": "原始数值为1985年美元/小时，不是月工资或年收入。",
                "source": "https://vincentarelbundock.github.io/Rdatasets/doc/AER/CPS1985.html",
            }
        },
    },
}


def registry_info():
    return [
        {"id": key, "label": value["label"], "task": value["task"]}
        for key, value in DATASETS.items()
    ]


def column_metadata(dataset_id, columns=None):
    spec = DATASETS.get(dataset_id, {})
    fields = spec.get("column_metadata", {})
    result = [
        {"name": name, **value}
        for name, value in fields.items()
        if columns is None or name in columns
    ]
    target = spec.get("target", "species" if dataset_id == "iris" else None)
    if spec.get("task") == "classification" and target and (columns is None or target in columns):
        result.append(
            {
                "name": target,
                "description": "分类标签；数值编码不表示大小、好坏或连续程度，具体类别映射以本次数据和target_encoding为准。",
            }
        )
    return result


def with_metadata(result, inherited_dataset=None):
    dataset_id = result.get("dataset", inherited_dataset)
    spec = DATASETS.get(dataset_id) if isinstance(dataset_id, str) else None
    value = dict(result)
    if spec:
        value["dataset_label"] = spec["label"]
        data = result.get("data")
        data = data if isinstance(data, dict) else {}
        fields = column_metadata(dataset_id, data.get("column_names"))
        if fields:
            value["data"] = {**data, "column_metadata": fields}
    if isinstance(result.get("methods"), dict):
        value["methods"] = {
            name: with_metadata(entry, dataset_id) for name, entry in result["methods"].items()
        }
    return value


def load(dataset_id, data_dir):
    entry = DATASETS.get(dataset_id)
    if entry is None:
        raise ValueError(f"未注册的本地数据集：{dataset_id}。可选：{', '.join(DATASETS)}。")
    path = Path(data_dir) / entry["file"]
    if not path.is_file():
        raise ValueError(f"本地数据集文件不存在：{path}")
    if entry["kind"] == "iris_metadata":
        return _load_iris(path, entry, dataset_id)
    return _load_tabular(path, entry, dataset_id)


def _load_iris(path, entry, dataset_id):
    pd = _pandas()
    frame = pd.read_csv(path, header=None)
    metadata = [str(value) for value in frame.iloc[0].tolist()]
    body = frame.iloc[1:].reset_index(drop=True)
    record_count = int(float(metadata[0]))
    feature_count = int(float(metadata[1]))
    class_names = metadata[2:]
    if body.shape[0] != record_count or feature_count != len(entry["features"]):
        raise ValueError("Iris 元数据与数据规模不一致。")
    values = body.iloc[:, :feature_count].to_numpy(dtype=float)
    target = body.iloc[:, feature_count].to_numpy(dtype=float)
    if set(np.unique(target)) - set(range(len(class_names))):
        raise ValueError("Iris 目标列取值与类别名不匹配。")
    excluded = [
        f"第 {index + 1} 列（导出索引或元数据）"
        for index in range(feature_count + 1, body.shape[1])
    ]
    return {
        "X": values,
        "y": target,
        "feature_names": list(entry["features"]),
        "target_name": "species",
        "task": entry["task"],
        "class_names": class_names,
        "excluded_columns": excluded,
        "dataset": dataset_id,
        "label": entry["label"],
    }


def _load_tabular(path, entry, dataset_id):
    pd = _pandas()
    frame = pd.read_csv(path)
    original = frame.copy()
    excluded = []
    limit = entry.get("limit")
    if isinstance(limit, int) and 0 < limit < frame.shape[0]:
        frame = frame.head(limit)
        excluded.append(f"只取前 {limit} 行（共超过 {limit} 行，按登记上限截取）")
    drop = [name for name in entry.get("drop", []) if name in frame.columns]
    if drop:
        frame = frame.drop(columns=drop)
    if entry["target"] == "last":
        target_name = frame.columns[-1]
    else:
        target_name = entry["target"]
    if target_name not in frame.columns:
        raise ValueError(f"数据集中没有目标列 {target_name}。")
    features = frame.drop(columns=[target_name])
    non_numeric = [
        str(name) for name in features.columns if not pd.api.types.is_numeric_dtype(features[name])
    ]
    if non_numeric:
        features = features.drop(columns=non_numeric)
        excluded.extend(f"{name}（非数值列）" for name in non_numeric)
    target = pd.to_numeric(frame[target_name], errors="coerce")
    features = features.apply(pd.to_numeric, errors="coerce")
    if features.shape[1] == 0 or features.shape[0] == 0:
        raise ValueError("数据集没有可用的数值特征或有效记录。")
    class_names = entry.get("class_names") or []
    if entry["task"] == "classification" and not class_names:
        class_names = [str(value) for value in sorted(np.unique(target.to_numpy(dtype=float)))]
    # Keep text/time/group columns available to domain methods without adding
    # their encodings to the registered numeric model features.
    from engine import tabular

    raw = original.loc[features.index].reset_index(drop=True)
    raw[target_name] = target.to_numpy(dtype=float)
    time_name = entry.get("time_column")
    if time_name and not pd.api.types.is_numeric_dtype(raw[time_name]):
        raw[time_name] = pd.to_datetime(raw[time_name], errors="raise")
    if time_name:
        order = raw.sort_values(time_name, kind="stable").index
        features = features.reset_index(drop=True).loc[order]
        target = target.reset_index(drop=True).loc[order]
        raw = raw.loc[order].reset_index(drop=True)
    table = tabular.Table(
        raw,
        features.reset_index(drop=True),
        list(features.columns),
        target_name,
        time_name,
        entry.get("group_column"),
        entry["task"],
    )
    table.input_features = list(features.columns)
    return {
        "table": table,
        "X": features.to_numpy(dtype=float),
        "y": target.to_numpy(dtype=float),
        "feature_names": [str(name) for name in features.columns],
        "target_name": target_name,
        "task": entry["task"],
        "class_names": list(class_names),
        "excluded_columns": excluded,
        "dataset": dataset_id,
        "label": entry["label"],
    }
