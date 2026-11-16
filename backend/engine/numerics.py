"""Reject invalid model outputs before thresholding or argmax can hide them."""

import numpy as np

from engine.registry import MethodError


def finite_values(values, label):
    result = np.asarray(values, dtype=float)
    if not result.size or not np.isfinite(result).all():
        raise MethodError(f"{label}含非有限值或为空，停止生成指标；请检查模型拟合与输入条件。")
    return result


def probabilities(values, rows, classes=None):
    result = finite_values(values, "预测概率")
    expected = (rows,) if classes is None else (rows, classes)
    if result.shape != expected:
        raise MethodError("预测概率形状与评价样本、类别不一致，停止生成指标。")
    if np.any(result < 0) or np.any(result > 1):
        raise MethodError("预测概率超出 [0, 1]，停止生成指标。")
    if classes is not None and not np.allclose(result.sum(axis=1), 1, rtol=0, atol=1e-8):
        raise MethodError("各类别预测概率之和不为 1，停止生成指标。")
    return result
