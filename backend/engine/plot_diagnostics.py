"""Classification figures use evaluated predictions, never fabricated inference."""

import numpy as np


def confusion_figure(context, name, actual, predicted, title, class_names=None):
    if not context.figures_enabled:
        return None
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import confusion_matrix
    except ImportError:
        context.warn("缺少分类诊断绘图库，未生成图像。")
        return None
    classes = np.unique(np.concatenate([np.asarray(actual), np.asarray(predicted)]))
    matrix = confusion_matrix(actual, predicted, labels=classes)
    labels = [
        str(class_names[int(value)] if class_names is not None else value) for value in classes
    ]
    fig, axis = plt.subplots(figsize=(4.8, 4.2))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(len(classes)), labels)
    axis.set_yticks(range(len(classes)), labels)
    axis.set_xlabel("预测类别")
    axis.set_ylabel("真实类别")
    axis.set_title(title)
    for row in range(len(classes)):
        for column in range(len(classes)):
            axis.text(
                column,
                row,
                int(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > matrix.max() / 2 else "#111827",
            )
    fig.colorbar(image, ax=axis, shrink=0.85)
    return context.save(fig, name)
