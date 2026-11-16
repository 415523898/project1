import hashlib
import math

import numpy as np

from agent.atomic_json import write_json

MAX_VALUES = 40000
MAX_ROWS = 4000
MAX_SERIES = 64


def coordinates(transform, axis):
    for expected, units in (
        (axis.transData, ("data", "data")),
        (axis.transAxes, ("axes_fraction", "axes_fraction")),
        (axis.get_xaxis_transform(), ("data", "axes_fraction")),
        (axis.get_yaxis_transform(), ("axes_fraction", "data")),
    ):
        if transform == expected:
            return dict(zip(("x", "y"), units, strict=True))
    return {"transform": type(transform).__name__, "units": "unresolved"}


def clean(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


class Budget:
    def __init__(self):
        self.remaining = MAX_VALUES

    def series(self, kind, values, **metadata):
        values = np.ma.asarray(values)
        shape = list(values.shape)
        if not shape:
            values = values.reshape(1)
            shape = [1]
        slices = [slice(0, min(size, 200)) for size in shape]
        width = math.prod(min(size, 200) for size in shape[1:])
        slices[0] = slice(0, min(shape[0], MAX_ROWS, self.remaining // max(1, width)))
        selected = values[tuple(slices)]
        self.remaining -= selected.size
        return {
            "kind": kind,
            **metadata,
            "source_shape": shape,
            "stored_shape": list(selected.shape),
            "truncated": list(selected.shape) != shape,
            "data": clean(selected.tolist()),
        }


def snapshot(figure, target):
    from matplotlib.collections import LineCollection, PathCollection, PolyCollection, QuadMesh
    from matplotlib.patches import Rectangle, Wedge

    budget, axes = Budget(), []
    for axis in figure.axes[:12]:
        series, unsupported = [], []

        def add(kind, values, **metadata):
            if len(series) < MAX_SERIES:
                series.append(budget.series(kind, values, **metadata))
            else:
                unsupported.append("series_limit")

        for line in axis.get_lines():
            add(
                "line",
                line.get_xydata(),
                columns=["x", "y"],
                label=line.get_label(),
                color=clean(line.get_color()),
                coordinates=coordinates(line.get_transform(), axis),
            )
        for image in axis.get_images():
            values = image.get_array()
            if values.ndim == 2:
                add(
                    "matrix",
                    values,
                    origin=image.origin,
                    extent=list(image.get_extent()),
                    coordinates=coordinates(image.get_transform(), axis),
                )
            else:
                unsupported.append("RGB image pixels are not a semantic description")
        for collection in axis.collections:
            if isinstance(collection, PathCollection):
                add(
                    "scatter",
                    collection.get_offsets(),
                    columns=["x", "y"],
                    label=collection.get_label(),
                    coordinates=coordinates(collection.get_offset_transform(), axis),
                )
            elif isinstance(collection, LineCollection):
                segments = collection.get_segments()
                if segments and len({np.asarray(item).shape for item in segments}) == 1:
                    add(
                        "segments",
                        segments,
                        columns=["x", "y"],
                        label=collection.get_label(),
                        coordinates=coordinates(collection.get_transform(), axis),
                    )
                else:
                    unsupported.append("irregular_segments")
            elif isinstance(collection, QuadMesh):
                add(
                    "matrix",
                    collection.get_array(),
                    label=collection.get_label(),
                    coordinates=coordinates(collection.get_transform(), axis),
                )
            elif isinstance(collection, PolyCollection):
                for path in collection.get_paths()[:MAX_SERIES]:
                    add(
                        "polygon",
                        path.vertices,
                        columns=["x", "y"],
                        label=collection.get_label(),
                        coordinates=coordinates(collection.get_transform(), axis),
                    )
            else:
                unsupported.append(type(collection).__name__)
        bars, wedges = [], []
        for patch in axis.patches:
            if isinstance(patch, Rectangle) and patch.get_data_transform() == axis.transData:
                bars.append([patch.get_x(), patch.get_y(), patch.get_width(), patch.get_height()])
            elif isinstance(patch, Wedge):
                wedges.append([patch.theta1, patch.theta2, patch.r, *patch.center])
            else:
                unsupported.append(type(patch).__name__)
        if bars:
            add(
                "bars",
                bars,
                columns=["x", "y", "width", "height"],
                coordinates={"x": "data", "y": "data"},
            )
        if wedges:
            add(
                "pie_geometry",
                wedges,
                columns=["theta1", "theta2", "radius", "center_x", "center_y"],
            )
        axes.append(
            {
                "index": len(axes),
                "title": axis.get_title()[:500],
                "x_label": axis.get_xlabel()[:500],
                "y_label": axis.get_ylabel()[:500],
                "x_scale": axis.get_xscale(),
                "y_scale": axis.get_yscale(),
                "x_limits": clean(axis.get_xlim()),
                "y_limits": clean(axis.get_ylim()),
                "x_tick_labels": [item.get_text()[:160] for item in axis.get_xticklabels()[:100]],
                "y_tick_labels": [item.get_text()[:160] for item in axis.get_yticklabels()[:100]],
                "annotations": [item.get_text()[:500] for item in axis.texts[:80]],
                "annotations_truncated": len(axis.texts) > 80,
                "unsupported": sorted(set(unsupported)),
                "series": series,
            }
        )
    value = {
        "schema": 1,
        "figure_name": target.name,
        "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source": "matplotlib_artists_at_save",
        "coordinate_system": "per_series_artist_coordinates",
        "axes": axes,
        "axes_truncated": len(figure.axes) > len(axes),
        "notes": [
            "实际绘图对象数据，不是原始源表或像素识别；null表示缺失/非有限值。",
            "坐标以各序列coordinates为准；axes_fraction是轴区间比例，未识别的变换不得按数据单位解释。",
            "饼图保存角度几何，不能据此恢复未提供的原始计数；未支持的对象单列，不推断。",
        ],
    }
    write_json(target.with_name(target.name + ".data.json"), clean(value))
