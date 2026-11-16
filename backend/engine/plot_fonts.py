"""Deterministic project-owned CJK font registration, independent of OS font caches."""

import threading
from pathlib import Path

FONT_PATH = Path(__file__).resolve().parents[1] / "agent/assets/fonts/NotoSansSC-Regular.otf"
_lock = threading.Lock()


def configure():
    import matplotlib
    from matplotlib import font_manager

    matplotlib.use("Agg")
    with _lock:
        if not FONT_PATH.is_file():
            raise FileNotFoundError(
                f"缺少实验中文字体：{FONT_PATH}；请随源码一起发布 backend/agent/assets/fonts。"
            )
        # addfont reads the standalone SC face directly; TTC discovery can expose only JP.
        if not any(
            Path(entry.fname).resolve() == FONT_PATH.resolve()
            for entry in font_manager.fontManager.ttflist
        ):
            font_manager.fontManager.addfont(str(FONT_PATH))
        family = font_manager.FontProperties(fname=str(FONT_PATH)).get_name()
        matplotlib.rcParams["font.family"] = ["sans-serif"]
        matplotlib.rcParams["font.sans-serif"] = [family, "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        matplotlib.rcParams["figure.dpi"] = 150
    return family
