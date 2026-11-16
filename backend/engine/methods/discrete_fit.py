"""Same unpenalized multinomial likelihood, evaluated without exp overflow.

statsmodels owns optimization, score, Hessian and covariance estimation. Only
the equivalent softmax/log-likelihood arithmetic is stabilized here.
"""

import warnings

import numpy as np
from scipy.special import logsumexp, softmax
from statsmodels.discrete.discrete_model import MNLogit
from statsmodels.tools.sm_exceptions import HessianInversionWarning, PerfectSeparationWarning

from engine.numerics import finite_values


class StableMNLogit(MNLogit):
    def cdf(self, X):
        return softmax(np.column_stack((np.zeros(len(X)), X)), axis=1)

    def loglikeobs(self, params):
        coefficients = np.asarray(params).reshape(self.K, -1, order="F")
        scores = np.column_stack((np.zeros(len(self.exog)), self.exog @ coefficients))
        return self.wendog * (scores - logsumexp(scores, axis=1, keepdims=True))

    def loglike(self, params):
        return self.loglikeobs(params).sum()

    def loglike_and_score(self, params):
        return self.loglike(params), self.score(params)


def fit_discrete(context, model, covariance):
    # Changing covariance must not silently choose a different optimizer.
    with warnings.catch_warnings(record=True) as messages:
        warnings.simplefilter("always")
        fitted = model.fit(method="bfgs", maxiter=200, disp=False, cov_type=covariance)
    finite_values(fitted.params, "拟合系数")
    finite_values([fitted.llf], "对数似然")
    converged = bool(fitted.mle_retvals.get("converged", False))
    # An optimizer stopping does not establish identifiable Wald inference.
    inference = converged and not any(
        issubclass(item.category, (HessianInversionWarning, PerfectSeparationWarning))
        for item in messages
    )
    try:
        information = -np.asarray(model.hessian(fitted.params), dtype=float)
        inference = inference and bool(
            np.isfinite(information).all()
            and np.linalg.matrix_rank(information) == information.shape[0]
        )
        errors = np.asarray(fitted.bse, dtype=float)
        inference = inference and bool(np.isfinite(errors).all() and (errors > 0).all())
    except (ValueError, np.linalg.LinAlgError):
        inference = False
    if not converged:
        context.warn("拟合在迭代上限内未收敛；预测仅供诊断，不可作为可靠效果或统计推断。")
    if not inference:
        context.warn(
            "系数推断不可用：可能存在完全/准完全分离、共线性或未收敛；"
            "当前数值解不能支持标准误、p 值和置信区间，不生成森林图。"
        )
    for message in dict.fromkeys(str(item.message) for item in messages):
        context.warn(f"拟合诊断：{message}")
    return fitted, converged, inference


def inference_arrays(fitted, available):
    if available:
        return fitted.bse, fitted.tvalues, fitted.pvalues
    missing = np.full(np.asarray(fitted.params).shape, np.nan)
    return missing, missing.copy(), missing.copy()
