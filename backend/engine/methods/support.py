import pandas as pd

from engine.registry import MethodError, apply_matrix, subset


def selected(context, key="columns"):
    names, matrix = subset(context.table, context.want(key))
    return names, matrix


def write_back(context, names, matrix):
    apply_matrix(context.table, names, matrix)


def frame(context, key="columns"):
    names, matrix = selected(context, key)
    return names, pd.DataFrame(matrix, columns=names)


def note_columns(context, names, total):
    if len(names) < total:
        context.warn(f"只在 {len(names)}/{total} 个特征上执行，其余列保持原样。")


def require_text(context, key, label, message):
    value = context.text(key)
    if not value:
        raise MethodError(message)
    return value
