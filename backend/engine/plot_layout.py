"""Shared layout pass for exported algorithm figures, including twin axes."""

import unicodedata


def wrapped(value, width):
    """Wrap full labels without losing identifiers or breaking math notation."""
    text = str(value)
    if "$" in text or "\\" in text:
        return text
    lines = []
    for paragraph in text.split("\n"):
        line, length = "", 0
        for char in paragraph:
            size = 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
            if length + size > width and line:
                lines.append(line)
                line, length = "", 0
            line += char
            length += size
        lines.append(line)
    return "\n".join(lines)


def _ticks(dimension):
    if not dimension.get_visible():
        return []
    low, high = sorted(dimension.get_view_interval())
    return [
        label
        for tick in dimension.get_major_ticks()
        if low <= tick.get_loc() <= high
        for label in (tick.label1, tick.label2)
        if label.get_visible() and label.get_text()
    ]


def _overlaps(labels, renderer):
    boxes = [label.get_window_extent(renderer) for label in labels]
    return any(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1 :])


def embedding_scatter(axis, x, y, table):
    """A continuous outcome uses a scale, rather than one legend row per value."""
    import math

    import pandas as pd

    labels = table.labels()
    if labels is None:
        axis.scatter(x, y, s=18, alpha=0.75)
    elif table.task == "regression":
        points = axis.scatter(x, y, c=table.numeric_target(), cmap="viridis", s=18, alpha=0.75)
        axis.figure.colorbar(points, ax=axis, label=table.target_name)
    else:
        values = pd.unique(labels)
        for label in values:
            mask = labels == label
            axis.scatter(x[mask], y[mask], s=18, alpha=0.75, label=str(label))
        if len(values) > 8:
            columns = max(1, math.ceil(len(values) / 20))
            width, height = axis.figure.get_size_inches()
            axis.figure.set_size_inches(min(24, max(width, 6 + 2.3 * columns)), max(height, 6))
            axis.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.02, 1), ncol=columns)
        else:
            axis.legend(fontsize=8)


def prepare(figure):
    """Reserve decoration space, then fit dense ticks at the actual render size."""
    for axis in figure.axes:
        if not axis.get_visible():
            continue
        for text, width in [(axis.title, 48), (axis.xaxis.label, 58), (axis.yaxis.label, 58)]:
            text.set_text(wrapped(text.get_text(), width))
        for dimension in (axis.xaxis, axis.yaxis):
            # Only fixed/category labels are rewritten; numeric and date
            # formatters must remain free to recompute after the axes resize.
            from matplotlib.category import StrCategoryFormatter
            from matplotlib.ticker import FixedFormatter

            if isinstance(dimension.get_major_formatter(), (FixedFormatter, StrCategoryFormatter)):
                locations = dimension.get_ticklocs()
                labels = dimension.get_ticklabels()
                if len(locations) == len(labels):
                    values = [wrapped(label.get_text(), 28) for label in labels]
                    if values != [label.get_text() for label in labels]:
                        dimension.set_ticks(locations, labels=values)
        legend = axis.get_legend()
        if legend:
            for text in legend.get_texts():
                text.set_text(wrapped(text.get_text(), 36))
    if figure._suptitle:
        figure._suptitle.set_text(wrapped(figure._suptitle.get_text(), 90))

    # Every registered plot passes through Context.save. This also reserves
    # room for twin-axis labels, colorbars, legends and the figure title.
    has_colorbar = any(getattr(axis, "_colorbar", None) is not None for axis in figure.axes)
    if has_colorbar:
        # Existing colorbars may own nested GridSpecs created by tight_layout;
        # switching those to constrained_layout is incompatible in Matplotlib.
        figure.set_layout_engine("tight", pad=1.6, w_pad=2.5, h_pad=2.5)
    else:
        figure.set_layout_engine("constrained", w_pad=0.14, h_pad=0.14, wspace=0.10, hspace=0.14)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    width, height = figure.get_size_inches()
    new_width, new_height = width, height
    changed = False
    for axis in figure.axes:
        if not axis.get_visible() or not axis.axison or axis.name == "3d":
            continue
        xlabels = _ticks(axis.xaxis)
        if len(xlabels) > 1 and _overlaps(xlabels, renderer):
            for label in xlabels:
                label.set_rotation(90)
                label.set_ha("center")
                label.set_va("top")
            changed = True
        ylabels = _ticks(axis.yaxis)
        if len(ylabels) > 1 and _overlaps(ylabels, renderer):
            required = max(label.get_window_extent(renderer).height + 5 for label in ylabels) * len(
                ylabels
            )
            new_height = max(
                new_height, min(24, height * required / max(axis.bbox.height, 1) * 1.12)
            )
            changed = True
    if new_width != width or new_height != height:
        figure.set_size_inches(new_width, new_height)
    if changed:
        figure.canvas.draw()
