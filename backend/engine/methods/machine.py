import math

import numpy as np
import pandas as pd

from engine import registry
from engine.numerics import finite_values, probabilities
from engine.plot_diagnostics import confusion_figure as _confusion_figure
from engine.registry import MethodError, numbers, register, table_of

EPS = 1e-12


def _data(context, columns=None):
    table = context.table
    matrix = table.matrix()
    if columns:
        if isinstance(columns, str):
            columns = [item.strip() for item in columns.split(",") if item.strip()]
        index = []
        for name in columns:
            if name not in table.feature_names:
                raise MethodError(f"列 {name} 不在特征中。")
            index.append(table.feature_names.index(name))
        matrix = matrix[:, index]
        table.feature_names = [str(name).strip() for name in columns]
        table.frame = table.frame[table.feature_names].copy()
    return matrix, table


def _split(context, matrix, target, test_size=None):
    if target is None:
        return matrix, matrix, None, None
    outcome = context.split_indices()
    evaluation_rows = context.evaluation_indices()
    # The shared split has now fitted imputation/encoding on training rows.
    matrix = context.table.matrix()
    columns = context.want("columns")
    if columns:
        columns = columns.split(",") if isinstance(columns, str) else columns
        matrix = matrix[
            :, [context.table.feature_names.index(str(name).strip()) for name in columns]
        ]
    if not outcome.has_test:
        return matrix, matrix, target, target
    train = outcome.train
    test = evaluation_rows
    if train.size < 3 or test.size < 2:
        raise MethodError(
            f"划分后训练集 {train.size} 条、测试集 {test.size} 条，样本太少无法拟合；"
            "请调小 test_size 或 validation_size。"
        )
    return matrix[train], matrix[test], target[train], target[test]


def _is_classification(target):
    series = pd.Series(target)
    if not pd.api.types.is_numeric_dtype(series):
        return True
    unique = pd.unique(series.dropna())
    return 2 <= len(unique) <= 10 and all(float(value).is_integer() for value in unique)


def _classification_report(model, x_test, y_test, classes):
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    predicted = model.predict(x_test)
    finite_values(predicted, "分类预测")
    probability = None
    if hasattr(model, "predict_proba"):
        probability = probabilities(model.predict_proba(x_test), len(y_test), len(classes))
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 6),
        "precision_macro": round(
            float(precision_score(y_test, predicted, average="macro", zero_division=0)), 6
        ),
        "recall_macro": round(
            float(recall_score(y_test, predicted, average="macro", zero_division=0)), 6
        ),
        "f1_macro": round(float(f1_score(y_test, predicted, average="macro", zero_division=0)), 6),
    }
    if len(classes) == 2 and probability is not None:
        positive_probability = probability[:, 1]
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test, positive_probability)), 6)
        except ValueError:
            metrics["roc_auc"] = None
    matrix = confusion_matrix(y_test, predicted, labels=classes)
    frame = pd.DataFrame(
        matrix, index=[f"真实:{c}" for c in classes], columns=[f"预测:{c}" for c in classes]
    )
    report = classification_report(y_test, predicted, output_dict=True, zero_division=0)
    rows = [
        {"class": str(key), **{k: round(float(v), 6) for k, v in value.items()}}
        for key, value in report.items()
        if isinstance(value, dict)
    ]
    return metrics, table_of(frame), table_of(pd.DataFrame(rows), limit=30), predicted


def _regression_report(model, x_test, y_test):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    predicted = model.predict(x_test)
    mse = float(mean_squared_error(y_test, predicted))
    return {
        "rmse": round(math.sqrt(mse), 6),
        "mae": round(float(mean_absolute_error(y_test, predicted)), 6),
        "r_squared": round(float(r2_score(y_test, predicted)), 6),
    }, predicted


def _scatter(context, predicted, actual, title, name):
    try:
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(5.5, 5))
        axis.scatter(actual, predicted, s=16, alpha=0.7)
        low = float(min(np.min(actual), np.min(predicted)))
        high = float(max(np.max(actual), np.max(predicted)))
        axis.plot([low, high], [low, high], color="#ef4444", linewidth=1)
        axis.set_xlabel("真实值")
        axis.set_ylabel("预测值")
        axis.set_title(title)
        axis.grid(alpha=0.3)
        return context.save(fig, name)
    except ImportError:
        return None


def _importance_figure(context, table, importances, name, title, top=15):
    try:
        import matplotlib.pyplot as plt

        values = np.asarray(importances, dtype=float)
        order = np.argsort(-values)[:top]
        fig, axis = plt.subplots(figsize=(7, max(3, order.size * 0.32)))
        axis.barh(
            [table.feature_names[index] for index in order][::-1],
            values[order][::-1],
            color="#4f7cff",
        )
        axis.set_xlabel("重要性")
        axis.set_title(title)
        axis.grid(alpha=0.3, axis="x")
        return context.save(fig, name)
    except ImportError:
        return None


def _residual_figure(context, name, actual, predicted, title):
    try:
        import matplotlib.pyplot as plt

        actual = np.asarray(actual, dtype=float)
        predicted = np.asarray(predicted, dtype=float)
        fig, axis = plt.subplots(figsize=(6, 4.5))
        axis.scatter(predicted, actual - predicted, s=16, alpha=0.7, color="#4f7cff")
        axis.axhline(0.0, color="#ef4444", linewidth=1)
        axis.set_xlabel("预测值")
        axis.set_ylabel("残差")
        axis.set_title(title)
        axis.grid(alpha=0.3)
        return context.save(fig, name)
    except ImportError:
        return None


def _diagnostic_figure(context, method_id, flag_key, model, task, parts):
    if not context.flag(flag_key, True):
        return None
    _, x_test, _, y_test = parts
    predicted = model.predict(x_test)
    label = registry.catalog.BY_ID[method_id]["label"]
    if task == "classification":
        return _confusion_figure(
            context, f"{method_id}_confusion", y_test, predicted, f"{label} 混淆矩阵"
        )
    return _residual_figure(context, f"{method_id}_residual", y_test, predicted, f"{label} 残差图")


def _supervised(context, method_id, build):
    matrix, table = _data(context, context.want("columns"))
    target = table.numeric_target()
    if target is None:
        raise MethodError(f"{table.task} 需要目标列。")
    task = "classification" if table.task == "classification" else "regression"
    x_train, x_test, y_train, y_test = _split(context, matrix, target)
    model = build()
    model.fit(x_train, y_train)
    metrics = {
        "task": task,
        "train_rows": int(x_train.shape[0]),
        "test_rows": int(x_test.shape[0]),
        "evaluation_rows": int(x_test.shape[0]),
        "features": int(matrix.shape[1]),
    }
    if not context.split_indices().has_test:
        metrics["test_rows"] = 0
    tables = {}
    figures = []
    if task == "classification":
        classes = np.unique(target)
        detail, confusion, report, predicted = _classification_report(
            model, x_test, y_test, classes
        )
        metrics.update(detail)
        tables["confusion_matrix"] = confusion
        tables["per_class"] = report
        metrics["classes"] = [str(value) for value in classes]
    else:
        detail, predicted = _regression_report(model, x_test, y_test)
        metrics.update(detail)
        name = _scatter(
            context,
            predicted,
            np.asarray(y_test, dtype=float),
            f"{registry.catalog.BY_ID[method_id]['label']} 预测对比",
            f"{method_id}_fit",
        )
        if name:
            figures.append(name)
    return model, metrics, tables, figures, matrix, table, task, (x_train, x_test, y_train, y_test)


@register("ml.kmeans")
def kmeans(context):
    from sklearn.cluster import KMeans
    from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

    matrix, table = _data(context, context.want("columns"))
    if matrix.shape[0] < 6:
        raise MethodError("K-Means 至少需要 6 个样本。")
    clusters = context.whole("clusters", 3, 2, max(2, matrix.shape[0] - 1))
    seed = context.whole("seed", 42, 0, 10**6)
    attempts = context.whole("n_init", 10, 1, 100)
    limit = context.whole("max_iter", 300, 1, 5000)
    tolerance = context.number("tol", 1e-4, 1e-8, 1.0)
    algorithm = context.text("algorithm", "lloyd", ("lloyd", "elkan"))
    init = context.text("init", "k-means++", ("k-means++", "random"))
    show_elbow = context.flag("elbow_plot", True)
    scaled, _, _ = registry.standardize(matrix)

    model = KMeans(
        n_clusters=clusters,
        random_state=seed,
        n_init=attempts,
        max_iter=limit,
        tol=tolerance,
        algorithm=algorithm,
        init=init,
    )
    labels = model.fit_predict(scaled)
    centres = model.cluster_centers_
    inertia = float(model.inertia_)
    silhouette = float(silhouette_score(scaled, labels)) if len(set(labels)) > 1 else None
    calinski = float(calinski_harabasz_score(scaled, labels)) if len(set(labels)) > 1 else None
    davies = float(davies_bouldin_score(scaled, labels)) if len(set(labels)) > 1 else None

    elbow = []
    for size in range(2, min(11, matrix.shape[0])):
        fitted = KMeans(
            n_clusters=size,
            random_state=seed,
            n_init=attempts,
            max_iter=limit,
            tol=tolerance,
            algorithm=algorithm,
            init=init,
        ).fit(scaled)
        elbow.append({"clusters": size, "inertia": round(float(fitted.inertia_), 6)})
    elbow_frame = pd.DataFrame(elbow)

    figures = []
    if not show_elbow:
        context.warn("已关闭肘部图，簇内平方和只保留在 elbow 表中。")
    try:
        import matplotlib.pyplot as plt

        if show_elbow:
            fig, axes = plt.subplots(1, 2, figsize=(11, 4))
            axes[0].plot(
                elbow_frame["clusters"], elbow_frame["inertia"], marker="o", color="#4f7cff"
            )
            axes[0].set_xlabel("聚类数")
            axes[0].set_ylabel("簇内平方和")
            axes[0].set_title("肘部图")
            axes[0].grid(alpha=0.3)
            if scaled.shape[1] >= 2:
                for label in sorted(set(labels)):
                    block = labels == label
                    axes[1].scatter(
                        scaled[block, 0], scaled[block, 1], s=16, alpha=0.75, label=f"簇{label}"
                    )
                axes[1].scatter(centres[:, 0], centres[:, 1], marker="x", s=90, color="#111827")
                axes[1].set_title("聚类结果（前两个特征）")
                axes[1].legend(fontsize=8)
                axes[1].grid(alpha=0.3)
        else:
            fig, axis = plt.subplots(figsize=(6, 4.5))
            if scaled.shape[1] >= 2:
                for label in sorted(set(labels)):
                    block = labels == label
                    axis.scatter(
                        scaled[block, 0], scaled[block, 1], s=16, alpha=0.75, label=f"簇{label}"
                    )
                axis.scatter(centres[:, 0], centres[:, 1], marker="x", s=90, color="#111827")
                axis.set_title("聚类结果（前两个特征）")
                axis.legend(fontsize=8)
                axis.grid(alpha=0.3)
        name = context.save(fig, "ml_kmeans")
        if name:
            figures.append(name)
    except ImportError:
        context.warn("未安装 matplotlib，跳过聚类图。")

    sizes = pd.Series(labels).value_counts().sort_index()
    rows = pd.DataFrame(
        {
            "cluster": [f"簇{index}" for index in sizes.index],
            "size": sizes.to_numpy(),
            "ratio": numbers(sizes.to_numpy() / len(labels), 4),
        }
    )
    table.frame = pd.DataFrame(scaled, columns=table.feature_names)
    return registry.result(
        "ml.kmeans",
        table,
        metrics={
            "clusters": clusters,
            "inertia": round(inertia, 6),
            "silhouette": None if silhouette is None else round(silhouette, 6),
            "calinski_harabasz": None if calinski is None else round(calinski, 6),
            "davies_bouldin": None if davies is None else round(davies, 6),
            "n_init": attempts,
            "max_iter": limit,
            "tol": float(tolerance),
            "algorithm": algorithm,
            "iterations": int(model.n_iter_),
            "rows": int(matrix.shape[0]),
        },
        tables={
            "cluster_sizes": table_of(rows, limit=30),
            "elbow": table_of(elbow_frame, limit=20),
        },
        notes=[
            "轮廓系数越接近 1 表示簇内紧密、簇间分离良好。",
            "K-Means 假设簇是球形且大小相近，对量纲敏感，这里已标准化。",
        ],
    )


@register("ml.hierarchical")
def hierarchical(context):
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist
    from sklearn.metrics import silhouette_score

    matrix, table = _data(context, context.want("columns"))
    if matrix.shape[0] < 4:
        raise MethodError("分层聚类至少需要 4 个样本。")
    method = context.text("linkage", "ward", ("ward", "complete", "average", "single"))
    metric = context.text(
        "metric", "euclidean", ("euclidean", "manhattan", "cosine", "correlation")
    )
    criterion = context.text("criterion", "maxclust", ("maxclust", "distance"))
    threshold = context.number("distance_threshold", None, 0.0, 10000.0)
    show_tree = context.flag("dendrogram", True)
    ordering = context.flag("optimal_ordering", False)
    centroids = context.flag("centroid_table", False)
    clusters = context.whole("clusters", 3, 2, max(2, matrix.shape[0] - 1))
    scaled, _, _ = registry.standardize(matrix)

    if method == "ward" and metric != "euclidean":
        raise MethodError(
            f"Ward 连接只能配合欧氏距离，当前距离度量为 {metric}，"
            f"请把距离度量改回 euclidean，或把连接方式换成 complete、average、single。"
        )

    distances = pdist(scaled, metric="cityblock" if metric == "manhattan" else metric)
    if not np.isfinite(distances).all():
        raise MethodError(
            f"距离度量 {metric} 在当前数据上产生了非有限距离，"
            f"请检查是否存在常数样本行，或改用 euclidean、manhattan。"
        )
    tree = linkage(distances, method=method)
    if ordering:
        from scipy.cluster.hierarchy import optimal_leaf_ordering

        tree = optimal_leaf_ordering(tree, distances)
    if criterion == "distance":
        cut = float(threshold) if threshold is not None else float(np.median(tree[:, 2]))
        labels = fcluster(tree, t=cut, criterion="distance")
    else:
        labels = fcluster(tree, t=clusters, criterion="maxclust")
    silhouette = float(silhouette_score(scaled, labels)) if len(set(labels)) > 1 else None

    figures = []
    if show_tree:
        try:
            import matplotlib.pyplot as plt
            from scipy.cluster.hierarchy import dendrogram

            fig, axis = plt.subplots(figsize=(10, 5))
            dendrogram(tree, ax=axis, truncate_mode="lastp", p=20, color_threshold=0)
            axis.set_title(f"层次聚类树状图（{method} 连接，{metric} 距离）")
            axis.set_xlabel("样本或簇")
            axis.set_ylabel("距离")
            name = context.save(fig, "ml_hierarchical")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过树状图。")

    sizes = pd.Series(labels).value_counts().sort_index()
    rows = pd.DataFrame(
        {"cluster": [f"簇{index}" for index in sizes.index], "size": sizes.to_numpy()}
    )
    tables = {"cluster_sizes": table_of(rows, limit=30)}
    if centroids:
        centre_frame = pd.DataFrame(
            [
                {
                    "cluster": f"簇{index}",
                    "size": int((labels == index).sum()),
                    **{
                        name: round(float(scaled[labels == index, position].mean()), 6)
                        for position, name in enumerate(table.feature_names)
                    },
                }
                for index in sorted(set(labels))
            ]
        )
        tables["centroids"] = table_of(centre_frame, limit=30)
    return registry.result(
        "ml.hierarchical",
        table,
        metrics={
            "clusters": clusters,
            "linkage": method,
            "metric": metric,
            "dendrogram": show_tree,
            "optimal_ordering": ordering,
            "rows": int(matrix.shape[0]),
            "silhouette": None if silhouette is None else round(silhouette, 6),
            "largest_cluster": int(sizes.max()),
            "smallest_cluster": int(sizes.min()),
        },
        tables=tables,
        notes=[
            "Ward 连接最小化簇内方差，通常产生大小相近的簇。",
            "单连接容易产生链式长簇，完整连接倾向紧凑的簇。",
        ],
    )


@register("ml.dbscan")
def dbscan(context):
    from sklearn.cluster import DBSCAN
    from sklearn.metrics import silhouette_score
    from sklearn.neighbors import NearestNeighbors

    matrix, table = _data(context, context.want("columns"))
    if matrix.shape[0] < 6:
        raise MethodError("DBSCAN 至少需要 6 个样本。")
    scaled, _, _ = registry.standardize(matrix)
    neighbours = context.whole("min_samples", 5, 2, 100)
    metric = context.text("metric", "euclidean", ("euclidean", "manhattan", "chebyshev"))
    radius = context.number("eps")
    percentile = context.number("eps_percentile", 90.0, 50.0, 99.0)
    if radius is None:
        distances, _ = (
            NearestNeighbors(n_neighbors=neighbours, metric=metric).fit(scaled).kneighbors(scaled)
        )
        radius = float(np.percentile(distances[:, -1], percentile))
        context.warn(
            f"未指定 eps，已按第 {percentile:g} 百分位的 {neighbours} 近邻距离取 {radius:.4f}。"
        )

    model = DBSCAN(eps=float(radius), min_samples=neighbours, metric=metric)
    labels = model.fit_predict(scaled)
    clusters = [value for value in set(labels) if value >= 0]
    noise = int((labels < 0).sum())
    silhouette = (
        float(silhouette_score(scaled[labels >= 0], labels[labels >= 0]))
        if len(clusters) > 1 and (labels >= 0).sum() > 2
        else None
    )

    sizes = (
        pd.Series(labels[labels >= 0]).value_counts().sort_index()
        if clusters
        else pd.Series(dtype=int)
    )
    rows = (
        pd.DataFrame({"cluster": [f"簇{index}" for index in sizes.index], "size": sizes.to_numpy()})
        if len(sizes)
        else pd.DataFrame({"cluster": ["无"], "size": [0]})
    )
    core_index = np.asarray(getattr(model, "core_sample_indices_", []), dtype=int)
    tables = {"cluster_sizes": table_of(rows, limit=30)}
    if context.flag("core_point_table", False):
        width = scaled.shape[1]
        frame = pd.DataFrame(
            scaled[core_index], columns=[f"z_{name}" for name in table.feature_names[:width]]
        )
        frame.insert(0, "cluster", labels[core_index])
        frame.insert(0, "core_index", core_index)
        tables["core_points"] = table_of(frame, limit=30)

    figures = []
    if scaled.shape[1] >= 2:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6.5, 5))
            axis.scatter(
                scaled[labels < 0, 0], scaled[labels < 0, 1], s=18, color="#9ca3af", label="噪声"
            )
            for label in clusters:
                block = labels == label
                axis.scatter(
                    scaled[block, 0], scaled[block, 1], s=18, alpha=0.8, label=f"簇{label}"
                )
            axis.set_title(f"DBSCAN（eps={float(radius):.3f}, min_samples={neighbours}, {metric}）")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            name = context.save(fig, "ml_dbscan")
            if name:
                figures.append(name)
        except ImportError:
            pass

    return registry.result(
        "ml.dbscan",
        table,
        metrics={
            "clusters": len(clusters),
            "noise_points": noise,
            "noise_ratio": round(noise / max(len(labels), 1), 6),
            "eps": round(float(radius), 6),
            "min_samples": neighbours,
            "metric": metric,
            "eps_percentile": percentile,
            "silhouette": None if silhouette is None else round(silhouette, 6),
            "core_points": int(core_index.size),
            "rows": int(matrix.shape[0]),
        },
        tables=tables,
        notes=[
            "DBSCAN 不需要预先指定簇数，能发现任意形状的簇并识别噪声。",
            "eps 太小会把大多数点判为噪声，太大会把所有点并成一个簇。",
        ],
    )


@register("ml.fcm")
def fcm(context):
    matrix, table = _data(context, context.want("columns"))
    if matrix.shape[0] < 6:
        raise MethodError("模糊 C 均值至少需要 6 个样本。")
    clusters = context.whole("clusters", 3, 2, max(2, matrix.shape[0] - 1))
    exponent = context.number("m", 2.0, 1.1, 5.0)
    tolerance = context.number("tolerance", 1e-5, 1e-10, 1e-2)
    limit = context.whole("max_iter", 200, 10, 2000)
    seed = context.whole("seed", 42, 0, 10**6)
    init = context.text("init", "random", ("random", "kmeans++", "centres"))
    scaled, _, _ = registry.standardize(matrix)

    rng = np.random.default_rng(seed)
    if init == "kmeans++":
        from sklearn.cluster import KMeans

        start = (
            KMeans(n_clusters=clusters, random_state=seed, n_init=10).fit(scaled).cluster_centers_
        )
    elif init == "centres":
        order = np.argsort(scaled[:, 0])
        pick = np.linspace(0, scaled.shape[0] - 1, clusters).astype(int)
        start = scaled[order[pick]]
    else:
        start = None
    if start is None:
        membership = rng.random((scaled.shape[0], clusters))
        membership = membership / membership.sum(axis=1, keepdims=True)
    else:
        distance0 = np.clip(
            np.linalg.norm(scaled[:, None, :] - start[None, :, :], axis=2), 1e-12, None
        )
        inverse0 = distance0 ** (-2.0 / (exponent - 1.0))
        membership = inverse0 / inverse0.sum(axis=1, keepdims=True)
    centres = start
    iterations = 0
    for iterations in range(1, limit + 1):
        powered = membership**exponent
        centres = (powered.T @ scaled) / powered.sum(axis=0, keepdims=True).T
        distance = np.linalg.norm(scaled[:, None, :] - centres[None, :, :], axis=2)
        distance = np.clip(distance, 1e-12, None)
        inverse = distance ** (-2.0 / (exponent - 1.0))
        updated = inverse / inverse.sum(axis=1, keepdims=True)
        if np.max(np.abs(updated - membership)) < tolerance:
            membership = updated
            break
        membership = updated

    converged = iterations < limit
    if not converged:
        context.warn(f"达到最大迭代 {limit} 次仍未收敛，结果可能不稳定，可提高最大迭代。")

    hard = membership.argmax(axis=1)
    fpc = float((membership**2).sum() / membership.shape[0])
    sizes = pd.Series(hard).value_counts().sort_index()
    rows = pd.DataFrame(
        {
            "cluster": [f"簇{index}" for index in sizes.index],
            "size": sizes.to_numpy(),
            "mean_membership": numbers(
                [membership[hard == index, index].mean() for index in sizes.index], 6
            ),
        }
    )
    centre_frame = pd.DataFrame(
        centres, columns=table.feature_names, index=[f"簇{index}" for index in range(clusters)]
    )
    tables = {
        "cluster_sizes": table_of(rows, limit=30),
        "centres": table_of(centre_frame.reset_index().rename(columns={"index": "cluster"})),
    }
    if context.flag("membership_table", False):
        members = pd.DataFrame(membership, columns=[f"簇{index}" for index in range(clusters)])
        members.insert(0, "max_membership", numbers(membership.max(axis=1), 6))
        members.insert(0, "hard_cluster", hard)
        members.insert(0, "row", np.arange(1, membership.shape[0] + 1))
        tables["membership"] = table_of(members, limit=40)

    figures = []
    if context.flag("membership_plot", True):
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6.5, 5))
            image = axis.imshow(membership.T, aspect="auto", cmap="viridis", vmin=0.0, vmax=1.0)
            axis.set_yticks(range(clusters), [f"簇{index}" for index in range(clusters)])
            axis.set_xlabel("样本序号")
            axis.set_ylabel("簇")
            axis.set_title(f"模糊隶属度热力图（m={exponent:g}）")
            fig.colorbar(image, ax=axis, label="隶属度", shrink=0.85)
            name = context.save(fig, "ml.fcm_membership")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过隶属度热力图。")

    return registry.result(
        "ml.fcm",
        table,
        metrics={
            "clusters": clusters,
            "exponent": exponent,
            "iterations": iterations,
            "max_iter": limit,
            "converged": converged,
            "init": init,
            "fuzzy_partition_coefficient": round(fpc, 6),
            "fuzzy_partition_entropy": round(
                float(
                    -(membership * np.log(np.clip(membership, 1e-12, None))).sum()
                    / membership.shape[0]
                ),
                6,
            ),
            "rows": int(scaled.shape[0]),
        },
        tables=tables,
        figures=figures,
        notes=[
            "模糊划分系数接近 1 说明划分清晰，接近 1/c 说明非常模糊。",
            "m 越大划分越模糊，常用 2。",
        ],
    )


def _forest(context, method_id, classifier, **extra):
    if classifier:
        from sklearn.ensemble import RandomForestClassifier as Model
    else:
        from sklearn.ensemble import RandomForestRegressor as Model

    seed = context.whole("seed", 42, 0, 10**6)
    estimators = context.whole("n_estimators", 200, 10, 2000)
    depth = context.whole("max_depth", None, 1, 100)
    leaf = context.whole("min_samples_leaf", 2, 1, 100)
    split = context.whole("min_samples_split", 2, 2, 200)
    features = context.text("max_features", "sqrt", ("sqrt", "log2", "all"))
    if classifier:
        criteria = ("gini", "entropy", "log_loss")
    else:
        criteria = ("squared_error", "absolute_error", "poisson")
    criterion = context.text("criterion", criteria[0])
    if criterion not in criteria:
        if not classifier and criterion in ("gini", "entropy", "log_loss"):
            criterion = "squared_error"
        else:
            raise MethodError(f"分裂准则只能是：{'、'.join(criteria)}。")
    samples = context.number("max_samples", 1.0, 0.1, 1.0)
    leaves = context.whole("max_leaf_nodes", None, 2, 5000)
    balance = context.text("class_weight", "none", ("none", "balanced", "balanced_subsample"))
    oob = context.flag("oob_score", True)
    if not classifier and criterion != "squared_error" and oob:
        oob = False
        context.warn(f"回归随机森林在 criterion={criterion} 下不支持袋外评分，已关闭袋外评分。")
    options = {} if samples >= 1.0 else {"max_samples": samples}
    if classifier and balance != "none":
        options["class_weight"] = balance
    if leaves is not None:
        options["max_leaf_nodes"] = leaves
    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context,
        method_id,
        lambda: Model(
            n_estimators=estimators,
            max_depth=depth,
            min_samples_leaf=leaf,
            min_samples_split=split,
            criterion=criterion,
            max_features=None if features == "all" else features,
            oob_score=oob,
            random_state=seed,
            **options,
            **extra,
        ),
    )
    if hasattr(model, "feature_importances_"):
        order = np.argsort(-model.feature_importances_)
        rows = pd.DataFrame(
            {
                "feature": [table.feature_names[index] for index in order],
                "importance": numbers(model.feature_importances_[order], 6),
            }
        )
        tables["feature_importance"] = table_of(rows, limit=60)
        metrics["top_feature"] = rows.iloc[0]["feature"]
        metrics["top_importance"] = rows.iloc[0]["importance"]
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, max(3, len(order) * 0.3)))
            shown = order[:15]
            axis.barh(
                [table.feature_names[index] for index in shown][::-1],
                model.feature_importances_[shown][::-1],
                color="#4f7cff",
            )
            axis.set_xlabel("重要性")
            axis.set_title("特征重要性")
            axis.grid(alpha=0.3, axis="x")
            name = context.save(fig, f"{method_id}_importance")
            if name:
                figures.append(name)
        except ImportError:
            pass
    metrics["oob_score"] = (
        round(float(model.oob_score_), 6) if hasattr(model, "oob_score_") else None
    )
    metrics["n_estimators"] = estimators
    metrics["min_samples_leaf"] = leaf
    metrics["max_features"] = features
    metrics["min_samples_split"] = split
    metrics["criterion"] = criterion
    metrics["max_samples"] = round(float(samples), 6)
    if depth:
        metrics["max_depth"] = depth
    return registry.result(
        method_id,
        table,
        metrics=metrics,
        tables=tables,
        notes=["随机森林对量纲不敏感，特征重要性基于不纯度下降，相关特征之间会互相分摊。"],
    )


@register("ml.random_forest")
def random_forest(context):
    target = context.table.numeric_target()
    classification = target is None or _is_classification(target)
    return _forest(context, "ml.random_forest", classification)


def _boosting(context, method_id, kind):
    from sklearn.ensemble import (
        AdaBoostClassifier,
        AdaBoostRegressor,
        GradientBoostingClassifier,
        GradientBoostingRegressor,
    )
    from sklearn.tree import DecisionTreeClassifier

    matrix, table = _data(context, context.want("columns"))
    target = table.numeric_target()
    if target is None:
        raise MethodError("需要目标列。")
    classification = table.task == "classification"
    seed = context.whole("seed", 42, 0, 10**6)
    estimators = context.whole("n_estimators", 200, 10, 2000)
    rate = context.number("learning_rate", 0.1, 1e-4, 2.0)
    depth = context.whole("max_depth", 3, 1, 30) if kind == "gradient" else None
    base_depth = context.whole("base_depth", None, 1, 10) if kind == "adaboost" else None
    subsample = context.number("subsample", 1.0, 0.1, 1.0) if kind == "gradient" else None
    column_share = context.number("max_features", 1.0, 0.1, 1.0) if kind == "gradient" else None
    leaf = context.whole("min_samples_leaf", 1, 1, 200) if kind == "gradient" else None
    split = context.whole("min_samples_split", 2, 2, 200) if kind == "gradient" else None
    loss = (
        context.text("loss", "linear", ("linear", "square", "exponential"))
        if kind == "adaboost"
        else None
    )
    show_errors = context.flag("error_curve", False) if kind == "adaboost" else False
    show_importance = context.flag("importance_plot", True) if kind == "adaboost" else False
    show_deviance = context.flag("deviance_plot", True) if kind == "gradient" else False

    def build():
        if kind == "adaboost":
            tree = (
                DecisionTreeClassifier(max_depth=base_depth, random_state=seed)
                if base_depth is not None
                else None
            )
            if classification:
                return AdaBoostClassifier(
                    estimator=tree, n_estimators=estimators, learning_rate=rate, random_state=seed
                )
            return AdaBoostRegressor(
                estimator=tree,
                n_estimators=estimators,
                learning_rate=rate,
                random_state=seed,
                loss=loss,
            )
        options = dict(
            n_estimators=estimators,
            learning_rate=rate,
            max_depth=depth,
            subsample=subsample,
            max_features=column_share,
            min_samples_leaf=leaf,
            min_samples_split=split,
            random_state=seed,
        )
        if classification:
            return GradientBoostingClassifier(**options)
        return GradientBoostingRegressor(**options)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, method_id, build
    )
    if hasattr(model, "feature_importances_"):
        order = np.argsort(-model.feature_importances_)
        rows = pd.DataFrame(
            {
                "feature": [table.feature_names[index] for index in order],
                "importance": numbers(model.feature_importances_[order], 6),
            }
        )
        tables["feature_importance"] = table_of(rows, limit=60)
        metrics["top_feature"] = rows.iloc[0]["feature"]
        if show_importance:
            name = _importance_figure(
                context,
                table,
                model.feature_importances_,
                f"{method_id}_importance",
                f"{registry.catalog.BY_ID[method_id]['label']} 特征重要性",
            )
            if name:
                figures.append(name)
    if hasattr(model, "estimator_errors_"):
        metrics["final_estimator_error"] = round(float(model.estimator_errors_[-1]), 6)
        metrics["first_estimator_error"] = round(float(model.estimator_errors_[0]), 6)
        if show_errors:
            curve = pd.DataFrame(
                {
                    "round": range(1, len(model.estimator_errors_) + 1),
                    "error": numbers(model.estimator_errors_, 6),
                    "weight": numbers(model.estimator_weights_, 6),
                }
            )
            tables["error_curve"] = table_of(curve, limit=80)
            try:
                import matplotlib.pyplot as plt

                fig, axis = plt.subplots(figsize=(7, 4.5))
                axis.plot(curve["round"], curve["error"], color="#ef4444", label="加权误差")
                axis.plot(curve["round"], curve["weight"], color="#4f7cff", label="学习器权重")
                axis.set_xlabel("轮次")
                axis.set_title("AdaBoost 每轮误差与学习器权重")
                axis.legend(fontsize=8)
                axis.grid(alpha=0.3)
                name = context.save(fig, f"{method_id}_error_curve")
                if name:
                    figures.append(name)
            except ImportError:
                pass
    if show_deviance and hasattr(model, "train_score_"):
        try:
            import matplotlib.pyplot as plt

            scores = np.asarray(model.train_score_, dtype=float)
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(np.arange(1, scores.size + 1), scores, color="#4f7cff")
            axis.set_xlabel("提升轮数")
            axis.set_ylabel("训练偏差")
            axis.set_title(f"{registry.catalog.BY_ID[method_id]['label']} 训练偏差曲线")
            axis.grid(alpha=0.3)
            name = context.save(fig, f"{method_id}_deviance")
            if name:
                figures.append(name)
        except ImportError:
            pass
    metrics["n_estimators"] = estimators
    metrics["learning_rate"] = rate
    if depth is not None:
        metrics["max_depth"] = depth
    if base_depth is not None:
        metrics["base_depth"] = base_depth
    if subsample is not None:
        metrics["subsample"] = round(float(subsample), 6)
        metrics["max_features"] = round(float(column_share), 6)
        metrics["min_samples_leaf"] = leaf
    return registry.result(
        method_id,
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            f"提升方法逐个拟合前一轮的残差/错分样本，学习率 {rate} 控制每棵树的贡献。",
            "提升对噪声敏感，迭代过多容易过拟合。",
        ],
    )


@register("ml.adaboost")
def adaboost(context):
    return _boosting(context, "ml.adaboost", "adaboost")


@register("ml.gbdt")
def gbdt(context):
    return _boosting(context, "ml.gbdt", "gradient")


@register("ml.xgboost")
def xgboost(context):
    import xgboost

    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    seed = context.whole("seed", 42, 0, 10**6)
    estimators = context.whole("n_estimators", 300, 10, 3000)
    depth = context.whole("max_depth", 6, 1, 30)
    rate = context.number("learning_rate", 0.1, 1e-4, 2.0)
    rows_share = context.number("subsample", 1.0, 0.1, 1.0)
    column_share = context.number("colsample_bytree", 1.0, 0.1, 1.0)
    penalty = context.number("reg_lambda", 1.0, 0.0, 100.0)
    penalty_l1 = context.number("reg_alpha", 0.0, 0.0, 100.0)
    gain = context.number("gamma", 0.0, 0.0, 100.0)
    weight = context.whole("min_child_weight", 1, 1, 100)
    importance_type = context.text("importance_type", "weight", ("weight", "gain", "cover"))
    show_importance = context.flag("importance_plot", True)

    def build():
        common = dict(
            n_estimators=estimators,
            max_depth=depth,
            learning_rate=rate,
            subsample=rows_share,
            colsample_bytree=column_share,
            reg_lambda=penalty,
            reg_alpha=penalty_l1,
            gamma=gain,
            min_child_weight=weight,
            importance_type=importance_type,
            random_state=seed,
            tree_method="hist",
            verbosity=0,
        )
        if classification:
            return xgboost.XGBClassifier(eval_metric="logloss", **common)
        return xgboost.XGBRegressor(**common)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.xgboost", build
    )
    importance = model.feature_importances_
    order = np.argsort(-importance)
    tables["feature_importance"] = table_of(
        pd.DataFrame(
            {
                "feature": [table.feature_names[index] for index in order],
                "importance": numbers(importance[order], 6),
            }
        ),
        limit=60,
    )
    if show_importance:
        name = _importance_figure(
            context, table, importance, "ml.xgboost_importance", "XGBoost 特征重要性"
        )
        if name:
            figures.append(name)
    metrics.update(
        {
            "n_estimators": estimators,
            "max_depth": depth,
            "learning_rate": rate,
            "subsample": round(float(rows_share), 6),
            "colsample_bytree": round(float(column_share), 6),
            "reg_lambda": round(float(penalty), 6),
            "min_child_weight": weight,
            "top_feature": table.feature_names[int(order[0])],
        }
    )
    return registry.result(
        "ml.xgboost",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "XGBoost 使用二阶导数的梯度提升与正则化项，通常比传统 GBDT 更准。",
            "max_depth 越大越容易过拟合；learning_rate 越小需要越多棵树。",
        ],
    )


@register("ml.lightgbm")
def lightgbm(context):
    import lightgbm

    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    seed = context.whole("seed", 42, 0, 10**6)
    estimators = context.whole("n_estimators", 300, 10, 3000)
    leaves = context.whole("num_leaves", 31, 2, 500)
    rate = context.number("learning_rate", 0.1, 1e-4, 2.0)
    rows_share = context.number("subsample", 1.0, 0.1, 1.0)
    column_share = context.number("colsample_bytree", 1.0, 0.1, 1.0)
    penalty = context.number("reg_lambda", 0.0, 0.0, 100.0)
    penalty_l1 = context.number("reg_alpha", 0.0, 0.0, 100.0)
    depth = context.whole("max_depth", 0, 0, 30)
    child = context.whole("min_child_samples", 20, 1, 200)
    importance_type = context.text("importance_type", "split", ("split", "gain"))
    show_importance = context.flag("importance_plot", True)

    def build():
        common = dict(
            n_estimators=estimators,
            num_leaves=leaves,
            learning_rate=rate,
            subsample=rows_share,
            subsample_freq=1 if rows_share < 1.0 else 0,
            colsample_bytree=column_share,
            reg_lambda=penalty,
            reg_alpha=penalty_l1,
            min_child_samples=child,
            importance_type=importance_type,
            random_state=seed,
            verbose=-1,
        )
        if depth > 0:
            common["max_depth"] = depth
        if classification:
            return lightgbm.LGBMClassifier(**common)
        return lightgbm.LGBMRegressor(**common)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.lightgbm", build
    )
    importance = model.feature_importances_
    order = np.argsort(-importance)
    tables["feature_importance"] = table_of(
        pd.DataFrame(
            {
                "feature": [table.feature_names[index] for index in order],
                "importance": numbers(importance[order], 6),
            }
        ),
        limit=60,
    )
    if show_importance:
        name = _importance_figure(
            context, table, importance, "ml.lightgbm_importance", "LightGBM 特征重要性"
        )
        if name:
            figures.append(name)
    metrics.update(
        {
            "n_estimators": estimators,
            "num_leaves": leaves,
            "learning_rate": rate,
            "subsample": round(float(rows_share), 6),
            "colsample_bytree": round(float(column_share), 6),
            "reg_lambda": round(float(penalty), 6),
            "min_child_samples": child,
            "top_feature": table.feature_names[int(order[0])],
        }
    )
    return registry.result(
        "ml.lightgbm",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "LightGBM 使用直方图算法与叶优先生长，训练更快但小样本更易过拟合。",
            "num_leaves 是控制复杂度的主要参数。",
        ],
    )


@register("ml.svm")
def svm(context):
    from sklearn.svm import SVC, SVR

    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    kernel = context.text("kernel", "rbf", ("rbf", "linear", "poly", "sigmoid"))
    penalty = context.number("C", 1.0, 1e-4, 1e4)
    gamma = context.text("gamma", "scale")
    degree = context.whole("degree", 3, 1, 10)
    constant = context.number("coef0", 0.0, 0.0, 10.0)
    epsilon = context.number("epsilon", 0.1, 0.0, 10.0)
    tolerance = context.number("tol", 1e-3, 1e-6, 1.0)
    balance = context.text("class_weight", "none", ("none", "balanced"))
    weights = None if balance == "none" else "balanced"
    show_diagnostic = context.flag("diagnostic_plot", True)

    def build():
        if classification:
            return SVC(
                kernel=kernel,
                C=penalty,
                gamma=gamma,
                degree=degree,
                coef0=constant,
                tol=tolerance,
                class_weight=weights,
                probability=True,
                random_state=context.whole("seed", 42, 0, 10**6),
            )
        return SVR(
            kernel=kernel,
            C=penalty,
            gamma=gamma,
            degree=degree,
            coef0=constant,
            tol=tolerance,
            epsilon=epsilon,
        )

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.svm", build
    )
    if classification:
        metrics["support_vectors"] = int(sum(model.n_support_))
        metrics["support_vector_ratio"] = round(float(sum(model.n_support_) / len(parts[2])), 6)
        metrics["class_weight"] = balance
    else:
        metrics["support_vectors"] = int(len(model.support_))
    if show_diagnostic:
        name = _diagnostic_figure(context, "ml.svm", "diagnostic_plot", model, task, parts)
        if name:
            figures.append(name)
    metrics.update(
        {
            "kernel": kernel,
            "C": penalty,
            "degree": degree,
            "coef0": round(float(constant), 6),
            "gamma": gamma,
        }
    )
    return registry.result(
        "ml.svm",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "SVM 只由支持向量决定边界，对量纲敏感，这里已标准化。",
            "C 越大越不允许错分，核函数决定边界形状。",
        ],
    )


@register("ml.knn")
def knn(context):
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor

    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    neighbours = context.whole("neighbours", 5, 1, 100)
    metric = context.text(
        "metric", "euclidean", ("euclidean", "manhattan", "chebyshev", "minkowski")
    )
    power = context.whole("p", 2, 1, 10)
    weights = context.text("weights", "uniform", ("uniform", "distance"))
    distance_table = context.flag("distance_sweep", False)
    sweep_max = context.whole("sweep_max", 20, 2, 100)
    show_sweep = context.flag("sweep_plot", True)

    def build():
        if classification:
            return KNeighborsClassifier(
                n_neighbors=neighbours, metric=metric, p=power, weights=weights
            )
        return KNeighborsRegressor(n_neighbors=neighbours, metric=metric, p=power, weights=weights)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.knn", build
    )
    upper = min(sweep_max + 1, max(2, len(parts[2]) - 1))
    sweep = []
    for size in range(1, upper):
        candidate = (
            KNeighborsClassifier(n_neighbors=size, metric=metric, p=power, weights=weights)
            if classification
            else KNeighborsRegressor(n_neighbors=size, metric=metric, p=power, weights=weights)
        )
        candidate.fit(parts[0], parts[2])
        if classification:
            score = float(candidate.score(parts[1], parts[3]))
            label = "accuracy"
        else:
            score = float(candidate.score(parts[1], parts[3]))
            label = "r_squared"
        sweep.append({"neighbours": size, label: round(score, 6)})
    sweep_frame = pd.DataFrame(sweep)
    tables["k_sweep"] = table_of(sweep_frame, limit=25)
    if distance_table:
        compared = []
        for size in range(1, upper):
            row = {"neighbours": size}
            for option in ("uniform", "distance"):
                candidate = (
                    KNeighborsClassifier(n_neighbors=size, metric=metric, p=power, weights=option)
                    if classification
                    else KNeighborsRegressor(
                        n_neighbors=size, metric=metric, p=power, weights=option
                    )
                )
                candidate.fit(parts[0], parts[2])
                row[option] = round(float(candidate.score(parts[1], parts[3])), 6)
            compared.append(row)
        tables["weight_sweep"] = table_of(pd.DataFrame(compared), limit=25)
    if show_sweep and sweep:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(sweep_frame["neighbours"], sweep_frame[label], marker="o", color="#4f7cff")
            axis.axvline(neighbours, color="#ef4444", linewidth=1, linestyle="--")
            axis.set_xlabel("近邻个数 k")
            axis.set_ylabel("测试集得分" if classification else "测试集 R²")
            axis.set_title(f"KNN 的 k 扫描曲线（当前 k={neighbours}）")
            axis.grid(alpha=0.3)
            name = context.save(fig, "ml.knn_sweep")
            if name:
                figures.append(name)
        except ImportError:
            pass
    metrics.update({"neighbours": neighbours, "metric": metric, "p": power, "weights": weights})
    return registry.result(
        "ml.knn",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "KNN 完全依赖距离度量，必须先标准化。",
            "k 太小方差大、k 太大会欠拟合；k_sweep 表给出测试集得分随 k 的变化。",
        ],
    )


@register("ml.nb")
def naive_bayes(context):
    from sklearn.naive_bayes import BernoulliNB, GaussianNB, MultinomialNB

    method = context.text("variant", "gaussian", ("gaussian", "multinomial", "bernoulli"))
    matrix, table = _data(context, context.want("columns"))
    target = table.numeric_target()
    if not _is_classification(target):
        raise MethodError("朴素贝叶斯用于分类任务。")
    if method in ("multinomial", "bernoulli") and (matrix < 0).any():
        raise MethodError("多项式与伯努利朴素贝叶斯要求特征非负。")
    smoothing = context.number("alpha", 1.0, 0.0, 100.0)
    variance = context.number("var_smoothing", 1e-9, 0.0, 1.0)
    fit_prior = context.flag("fit_prior", True)
    threshold = context.number("binarize", 0.0, 0.0, 100.0)
    declared = context.want("class_prior")
    priors = None
    if declared not in (None, ""):
        try:
            priors = [
                float(part) for part in str(declared).replace("，", ",").split(",") if part.strip()
            ]
        except ValueError:
            raise MethodError("自定义类别先验需要形如 0.6,0.4 的逗号分隔数字。")
        if not priors or min(priors) < 0:
            raise MethodError("自定义类别先验必须是非负数字。")
        if not fit_prior:
            raise MethodError("自定义类别先验要求勾选「从数据估计类别先验」。")

    def build():
        if method == "gaussian":
            return GaussianNB(priors=priors, var_smoothing=variance)
        if method == "bernoulli":
            return BernoulliNB(
                alpha=smoothing, binarize=threshold, fit_prior=fit_prior, class_prior=priors
            )
        return MultinomialNB(alpha=smoothing, fit_prior=fit_prior, class_prior=priors)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.nb", build
    )
    prior = getattr(model, "class_prior_", None)
    if prior is not None:
        metrics["class_prior"] = numbers(prior, 6)
    metrics["variant"] = method
    metrics["fit_prior"] = fit_prior
    if priors is not None:
        metrics["declared_class_prior"] = numbers(priors, 6)
    if method == "gaussian":
        metrics["var_smoothing"] = float(variance)
    else:
        metrics["alpha"] = smoothing
    if method == "bernoulli":
        metrics["binarize"] = round(float(threshold), 6)
    if context.flag("confusion_plot", True):
        name = _diagnostic_figure(context, "ml.nb", "confusion_plot", model, task, parts)
        if name:
            figures.append(name)
    return registry.result(
        "ml.nb",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "朴素贝叶斯假设特征在给定类别下条件独立，这个假设通常不成立但仍有效。",
            "高斯版本适连续特征，多项式版本适合词频等计数特征。",
        ],
    )


@register("ml.mlp")
def mlp(context):
    from sklearn.neural_network import MLPClassifier, MLPRegressor

    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    hidden = context.text("hidden", "100,50")
    try:
        layers = tuple(int(part.strip()) for part in str(hidden).split(",") if part.strip())
    except ValueError:
        raise MethodError("hidden 需要形如 100,50 的逗号分隔整数。")
    if not layers or len(layers) > 5 or max(layers) > 2000:
        raise MethodError("隐藏层最多 5 层、每层不超过 2000 个神经元。")
    seed = context.whole("seed", 42, 0, 10**6)
    limit = context.whole("max_iter", 800, 50, 20000)
    activation = context.text("activation", "relu", ("relu", "tanh", "logistic"))
    solver = context.text("solver", "adam", ("adam", "sgd", "lbfgs"))
    penalty = context.number("alpha", 0.0001, 0.0, 10.0)
    learning = context.number("learning_rate_init", 0.001, 1e-5, 1.0)
    tolerance = context.number("tol", 1e-4, 1e-8, 1.0)
    early = context.flag("early_stopping", False)
    show_loss = context.flag("loss_plot", True)
    batch = context.text("batch_size", "auto")
    if batch != "auto":
        try:
            batch = int(float(batch))
        except ValueError:
            raise MethodError("批大小只支持 auto 或正整数。")
        if batch < 1:
            raise MethodError("批大小只支持 auto 或正整数。")
    else:
        batch = "auto"

    def build():
        if classification:
            return MLPClassifier(
                hidden_layer_sizes=layers,
                activation=activation,
                alpha=penalty,
                solver=solver,
                tol=tolerance,
                early_stopping=early,
                max_iter=limit,
                random_state=seed,
                learning_rate_init=learning,
                batch_size=batch,
            )
        return MLPRegressor(
            hidden_layer_sizes=layers,
            activation=activation,
            alpha=penalty,
            solver=solver,
            tol=tolerance,
            early_stopping=early,
            max_iter=limit,
            random_state=seed,
            learning_rate_init=learning,
            batch_size=batch,
        )

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.mlp", build
    )
    if hasattr(model, "loss_curve_") and model.loss_curve_:
        curve = pd.DataFrame(
            {
                "iteration": range(1, len(model.loss_curve_) + 1),
                "loss": numbers(model.loss_curve_, 6),
            }
        )
        tables["loss_curve"] = table_of(curve, limit=60)
        if show_loss:
            try:
                import matplotlib.pyplot as plt

                fig, axis = plt.subplots(figsize=(7, 4.5))
                axis.plot(curve["iteration"], curve["loss"], color="#4f7cff")
                axis.set_yscale("log")
                axis.set_xlabel("迭代轮次")
                axis.set_ylabel("训练损失")
                axis.set_title(f"MLP 训练损失曲线（{solver} 优化器）")
                axis.grid(alpha=0.3)
                name = context.save(fig, "ml.mlp_loss")
                if name:
                    figures.append(name)
            except ImportError:
                pass
    metrics.update(
        {
            "hidden_layers": list(layers),
            "activation": activation,
            "alpha": penalty,
            "learning_rate_init": float(learning),
            "batch_size": batch,
            "iterations": int(model.n_iter_),
            "final_loss": round(float(model.loss_), 6),
        }
    )
    return registry.result(
        "ml.mlp",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "神经网络对量纲敏感，需要标准化；这里用的是全连接前馈网络。",
            "损失曲线仍在明显下降说明迭代次数不够。",
        ],
    )


@register("ml.rbf")
def rbf(context):
    matrix, table = _data(context, context.want("columns"))
    target = table.numeric_target()
    if target is None:
        raise MethodError("RBF 网络需要目标列。")
    classification = table.task == "classification"
    centres_count = context.whole("centres", min(30, max(2, matrix.shape[0] // 5)), 2, 200)
    seed = context.whole("seed", 42, 0, 10**6)

    x_train, x_test, y_train, y_test = _split(context, matrix, target)
    centre, spread = x_train.mean(axis=0), x_train.std(axis=0)
    spread = np.where(spread <= EPS, 1.0, spread)
    x_train, x_test = (x_train - centre) / spread, (x_test - centre) / spread
    rng = np.random.default_rng(seed)
    selection = context.text("centres_init", "kmeans", ("kmeans", "random"))
    pick = rng.choice(x_train.shape[0], size=min(centres_count, x_train.shape[0]), replace=False)
    centres = x_train[pick]

    from sklearn.cluster import KMeans

    if selection == "kmeans":
        fitted_centres = (
            KMeans(n_clusters=centres.shape[0], random_state=seed, n_init=10)
            .fit(x_train)
            .cluster_centers_
        )
    else:
        fitted_centres = centres
    width = context.number("width", None, 1e-6, 1000.0)
    factor = context.number("width_factor", 1.0, 0.1, 5.0)
    bias = context.flag("bias", True)
    penalty = context.number("penalty", 0.0, 0.0, 100.0)
    show_fit = context.flag("fit_plot", True)
    if width is None:
        distances = np.linalg.norm(x_train[:, None, :] - fitted_centres[None, :, :], axis=2)
        positive = distances[distances > 0]
        width = float(np.median(positive)) if positive.size else 1.0
    width = max(float(width) * float(factor), 1e-6)

    def features(block):
        distance = np.linalg.norm(block[:, None, :] - fitted_centres[None, :, :], axis=2)
        return np.exp(-(distance**2) / (2 * width**2))

    train_matrix = features(x_train)
    test_matrix = features(x_test)
    if bias:
        train_matrix = np.column_stack([np.ones(x_train.shape[0]), train_matrix])
        test_matrix = np.column_stack([np.ones(x_test.shape[0]), test_matrix])
    if penalty > 0:
        gram = train_matrix.T @ train_matrix
        ridge = np.eye(gram.shape[0]) * float(penalty)
        output_target = (
            (y_train[:, None] == np.unique(y_train)[None, :]).astype(float)
            if classification
            else y_train
        )
        coefficients = np.linalg.solve(gram + ridge, train_matrix.T @ output_target)
    else:
        output_target = (
            (y_train[:, None] == np.unique(y_train)[None, :]).astype(float)
            if classification
            else y_train
        )
        coefficients, *_ = np.linalg.lstsq(train_matrix, output_target, rcond=None)
    predicted = finite_values(test_matrix @ coefficients, "RBF 预测得分")

    metrics = {
        "centres": int(fitted_centres.shape[0]),
        "width": round(width, 6),
        "width_factor": factor,
        "centres_init": selection,
        "train_rows": int(x_train.shape[0]),
        "test_rows": int(x_test.shape[0]),
        "features": int(matrix.shape[1]),
    }
    tables = {}
    figures = []
    if classification:
        rounded = np.unique(y_train)[np.argmax(predicted, axis=1)]
        accuracy = float((rounded == y_test).mean())
        metrics.update(
            {
                "task": "classification",
                "accuracy": round(accuracy, 6),
                "classes": [str(value) for value in np.unique(target)],
            }
        )
        if show_fit:
            name = _confusion_figure(
                context, "ml.rbf_confusion", y_test, rounded, "RBF 网络混淆矩阵"
            )
            if name:
                figures.append(name)
    else:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        metrics.update(
            {
                "task": "regression",
                "rmse": round(math.sqrt(float(mean_squared_error(y_test, predicted))), 6),
                "mae": round(float(mean_absolute_error(y_test, predicted)), 6),
                "r_squared": round(float(r2_score(y_test, predicted)), 6),
            }
        )
        if show_fit:
            name = _scatter(
                context,
                predicted,
                np.asarray(y_test, dtype=float),
                "RBF 网络预测对比",
                "ml.rbf_fit",
            )
            if name:
                figures.append(name)
    return registry.result(
        "ml.rbf",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=[
            "RBF 网络用高斯核把输入映射到高维，再线性组合输出。",
            "分类输出对训练类别使用独立指示目标，取最大得分类别；类别数值大小不参与回归。",
            "中心由 K-Means 选取，未指定 width 时宽度取训练样本到中心距离的中位数。",
        ],
    )


@register("ml.trees")
def trees(context):
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    variant = context.text("variant", "cart", ("cart", "entropy"))
    matrix, table = _data(context, context.want("columns"))
    table.numeric_target()
    classification = table.task == "classification"
    depth = context.whole("max_depth", 5, 1, 50)
    leaf = context.whole("min_samples_leaf", 3, 1, 1000)
    split = context.whole("min_samples_split", 2, 2, 200)
    leaves = context.whole("max_leaf_nodes", None, 2, 5000)
    features = context.text("max_features", "all", ("all", "sqrt", "log2"))
    splitter = context.text("splitter", "best", ("best", "random"))
    pruning = context.number("ccp_alpha", 0.0, 0.0, 1.0)
    show_structure = context.flag("structure_plot", True)

    def build():
        common = dict(
            max_depth=depth,
            min_samples_leaf=leaf,
            min_samples_split=split,
            max_leaf_nodes=leaves,
            max_features=None if features == "all" else features,
            splitter=splitter,
            ccp_alpha=pruning,
            random_state=context.whole("seed", 42, 0, 10**6),
        )
        if classification:
            criterion = "entropy" if variant == "entropy" else "gini"
            return DecisionTreeClassifier(criterion=criterion, **common)
        return DecisionTreeRegressor(**common)

    model, metrics, tables, figures, matrix, table, task, parts = _supervised(
        context, "ml.trees", build
    )
    from sklearn.tree import export_text

    rules = export_text(model, feature_names=list(table.feature_names), max_depth=4)
    metrics.update(
        {
            "variant": variant,
            "max_depth": depth,
            "min_samples_leaf": leaf,
            "max_leaf_nodes": leaves,
            "ccp_alpha": round(float(pruning), 6),
            "actual_depth": int(model.get_depth()),
            "leaves": int(model.get_n_leaves()),
        }
    )
    tables["rules"] = {
        "columns": ["决策规则"],
        "rows": [[line] for line in rules.splitlines()[:60]],
        "total_rows": len(rules.splitlines()),
        "truncated": len(rules.splitlines()) > 60,
    }
    if hasattr(model, "feature_importances_"):
        order = np.argsort(-model.feature_importances_)
        tables["feature_importance"] = table_of(
            pd.DataFrame(
                {
                    "feature": [table.feature_names[index] for index in order],
                    "importance": numbers(model.feature_importances_[order], 6),
                }
            ),
            limit=60,
        )
    if show_structure:
        try:
            import matplotlib.pyplot as plt
            from sklearn.tree import plot_tree

            fig, axis = plt.subplots(figsize=(12, 6))
            plot_tree(
                model,
                ax=axis,
                feature_names=list(table.feature_names),
                filled=True,
                rounded=True,
                max_depth=3,
                fontsize=7,
            )
            axis.set_title(f"CART 决策树结构（最多显示 3 层，{variant}）")
            name = context.save(fig, "ml.trees_structure")
            if name:
                figures.append(name)
        except ImportError:
            pass
    return registry.result(
        "ml.trees",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "实际执行 sklearn 的 CART 二叉决策树；entropy 仅改变不纯度准则，不代表 C4.5、CHAID 或 QUEST。",
            "树不需要标准化，且规则可以直接读出。",
        ],
    )


@register("ml.lda_qda")
def lda_qda(context):
    from sklearn.discriminant_analysis import (
        LinearDiscriminantAnalysis,
        QuadraticDiscriminantAnalysis,
    )

    variant = context.text("variant", "lda", ("lda", "qda"))
    solver = context.text("solver", "svd", ("svd", "lsqr", "eigen"))
    regularisation = context.number("reg_param", 0.1, 0.0, 1.0)
    tolerance = context.number("tol", 1e-4, 1e-8, 1.0)
    store_covariance = context.flag("store_covariance", False)
    show_confusion = context.flag("confusion_plot", True)
    declared = context.want("priors")
    priors = None
    if declared not in (None, ""):
        try:
            priors = [
                float(part) for part in str(declared).replace("，", ",").split(",") if part.strip()
            ]
        except ValueError:
            raise MethodError("自定义类别先验需要形如 0.6,0.4 的逗号分隔数字。")
        if not priors or min(priors) < 0:
            raise MethodError("自定义类别先验必须是非负数字。")
    matrix, table = _data(context, context.want("columns"))
    target = table.numeric_target()
    if not _is_classification(target):
        raise MethodError("判别分析用于分类任务。")
    classes = sorted({float(value) for value in np.asarray(target, dtype=float)})
    if len(classes) < 2:
        raise MethodError("判别分析至少需要两个类别。")
    if priors is not None and len(priors) != len(classes):
        raise MethodError(f"自定义类别先验需要 {len(classes)} 个数字，与数据里的类别数一致。")

    def build():
        if variant == "lda":
            options = {
                "solver": solver,
                "tol": tolerance,
                "priors": priors,
                "store_covariance": bool(store_covariance),
            }
            if solver != "svd":
                options["shrinkage"] = "auto"
            return LinearDiscriminantAnalysis(**options)
        return QuadraticDiscriminantAnalysis(
            reg_param=regularisation,
            tol=tolerance,
            priors=priors,
            store_covariance=bool(store_covariance),
        )

    try:
        model, metrics, tables, figures, matrix, table, task, parts = _supervised(
            context, "ml.lda_qda", build
        )
    except MethodError as error:
        raise MethodError(f"{variant.upper()} 拟合失败：{error}")

    metrics["variant"] = variant
    metrics["classes"] = [str(value) for value in classes]
    metrics["features"] = int(matrix.shape[1])
    metrics["tol"] = tolerance
    metrics["store_covariance"] = bool(store_covariance)
    if priors is not None:
        metrics["declared_class_prior"] = numbers(priors, 6)
    if show_confusion:
        name = _diagnostic_figure(context, "ml.lda_qda", "confusion_plot", model, task, parts)
        if name:
            figures.append(name)
    if store_covariance:
        covariance = getattr(model, "covariance_", None)
        if covariance is not None:
            frame = pd.DataFrame(np.atleast_2d(covariance), columns=list(table.feature_names))
            tables["covariance"] = table_of(
                frame.reset_index().rename(columns={"index": "row"}), limit=40
            )
    if variant == "lda":
        if solver != "svd":
            metrics["solver"] = solver
        if hasattr(model, "explained_variance_ratio_"):
            metrics["explained_variance_ratio"] = numbers(model.explained_variance_ratio_, 6)
        coefficients = getattr(model, "coef_", None)
        if coefficients is not None:
            frame = pd.DataFrame(
                np.atleast_2d(coefficients),
                index=coefficient_labels(len(classes)),
                columns=list(table.feature_names),
            )
            tables["coefficients"] = table_of(
                frame.reset_index().rename(columns={"index": "class"}), limit=40
            )
            metrics["coefficient_rows"] = int(np.atleast_2d(coefficients).shape[0])
    else:
        metrics["regularisation"] = regularisation
        priors = getattr(model, "priors_", None)
        if priors is not None:
            metrics["class_prior"] = numbers(priors, 6)
    return registry.result(
        "ml.lda_qda",
        table,
        metrics=metrics,
        tables=tables,
        notes=[
            "LDA 假设各类协方差相同，QDA 允许不同协方差但需要更多样本。",
            "二分类时 sklearn 只给出一个判别方向的系数（正类相对负类），多分类时才每个类别一行。",
            "LDA 也可以用于有监督降维，最多降到 类别数−1 维。",
        ],
    )


def coefficient_labels(class_count):
    if class_count == 2:
        return ["边界方向（正类相对负类）"]
    return [f"类别 {index}" for index in range(class_count)]
