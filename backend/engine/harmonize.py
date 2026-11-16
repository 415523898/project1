import codecs
import csv
import io
import json
import math
import re
import unicodedata
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError as error:
    raise ImportError("统一输入层需要 numpy 与 pandas。") from error


class HarmonizeError(ValueError):
    pass


class HarmonizeInputError(HarmonizeError):
    pass


ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1")
DELIMITERS = (",", "\t", ";", "|", " ")
DELIMITER_LABELS = {
    ",": "逗号",
    "\t": "制表符",
    ";": "分号",
    "|": "竖线",
    " ": "空格对齐",
    "": "单列（无分隔符）",
}
SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls", ".json")
SNIFF_LINES = 60
HEADER_SCAN_ROWS = 12
HEADER_SEARCH_ROWS = 4
TYPE_COVERAGE = 0.8
HEADER_NUMERIC_RATIO = 0.5
MIN_ENCODING_SCORE = 0.55
MISSING_MARKERS = (
    "",
    "na",
    "n/a",
    "n.a.",
    "nan",
    "null",
    "none",
    "nil",
    "missing",
    "unknown",
    "not available",
    "not applicable",
    "-",
    "--",
    "---",
    "?",
    "??",
    "？",
    "无",
    "未知",
    "空",
    "缺",
    "缺失",
    "未填",
    "没有",
)
BOOL_TRUE = {"是", "y", "yes", "true", "t", "真", "有", "成立", "对", "正确", "1", "1.0"}
BOOL_FALSE = {"否", "n", "no", "false", "f", "假", "无", "不成立", "错", "错误", "0", "0.0"}
TARGET_CANDIDATES = (
    "target",
    "label",
    "class",
    "y",
    "outcome",
    "标签",
    "目标",
    "目标列",
    "类别",
    "结果",
)
CURRENCY = "￥¥$€£₩₹"
MAGNITUDES = {
    "万": 1e4,
    "萬": 1e4,
    "亿": 1e8,
    "億": 1e8,
    "千": 1e3,
    "百": 1e2,
    "k": 1e3,
    "K": 1e3,
    "w": 1e4,
    "W": 1e4,
    "m": 1e6,
    "M": 1e6,
    "g": 1e9,
}
NUMERIC_STOPWORDS = ("错误", "失败", "无法", "缺少", "为空", "全部", "结论", "口径")
COLUMN_TYPES = ("number", "boolean", "date", "text", "empty")
RAW_SUFFIX = "_原始值"
INTEGER_PATTERN = re.compile(r"\A[+-]?\d+(?:[eE][+-]?\d+)?\Z")
DECIMAL_PATTERN = re.compile(r"\A[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?\Z")
SCIENTIFIC_PATTERN = re.compile(r"\A[+-]?\d+(?:\.\d+)?[eE][+-]?\d+\Z")
THOUSANDS_PATTERN = re.compile(r"\A[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?\Z")
MAGNITUDE_PATTERN = re.compile(r"\A([+-]?\d+(?:\.\d+)?)\s*([万萬亿億千百kKwWmMgG])\Z")
DATE_PATTERNS = (
    re.compile(
        r"\A(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})"
        r"(?:[ T](\d{1,2})\s*[:：]\s*(\d{2})(?:\s*[:：]\s*(\d{2}))?)?\Z"
    ),
    re.compile(
        r"\A(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})"
        r"(?:[ T](\d{1,2})\s*[:：]\s*(\d{2})(?:\s*[:：]\s*(\d{2}))?)?\Z"
    ),
    re.compile(
        r"\A(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"
        r"(?:\s*(\d{1,2})\s*[:：时]\s*(\d{1,2})\s*分?(?:\s*(\d{1,2})\s*秒?)?)?\Z"
    ),
    re.compile(r"\A(19\d{2}|20\d{2})(\d{2})(\d{2})(?:[ T]?(\d{2})(\d{2})(\d{2})?)?\Z"),
    re.compile(r"\A(19\d{2}|20\d{2})\s*[-/]\s*(\d{1,2})\Z"),
)
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\ufeff]")
BRACKET_PATTERN = re.compile(r"[\[\]（）()【】{}<>《》]")
PUNCT_PATTERN = re.compile(r"[^\w\u4e00-\u9fff]+")
SPACE_PATTERN = re.compile(r"\s+")


class HarmonizeReport:
    def __init__(self, name=None):
        self.name = name or "未命名输入"
        self.entries = []
        self.steps = []

    def add(self, step, message, level="info", detail=None):
        entry = {"level": level, "step": step, "message": message}
        if detail is not None:
            entry["detail"] = detail
        self.entries.append(entry)
        if step not in self.steps:
            self.steps.append(step)
        return entry

    def info(self, step, message, detail=None):
        return self.add(step, message, "info", detail)

    def warn(self, step, message, detail=None):
        return self.add(step, message, "warn", detail)

    def error(self, step, message, detail=None):
        return self.add(step, message, "error", detail)

    def of(self, step):
        return [entry for entry in self.entries if entry["step"] == step]

    def has(self, level):
        return any(entry["level"] == level for entry in self.entries)

    def warnings(self):
        return [entry["message"] for entry in self.entries if entry["level"] == "warn"]

    def errors(self):
        return [entry["message"] for entry in self.entries if entry["level"] == "error"]

    def lines(self):
        rows = [f"### {self.name}", ""]
        for step in self.steps:
            rows.append(f"**{step}**")
            for entry in self.of(step):
                mark = {"info": "·", "warn": "!", "error": "×"}.get(entry["level"], "·")
                rows.append(f"- {mark} {entry['message']}")
            rows.append("")
        return rows

    def text(self):
        return "\n".join(self.lines()).rstrip() + "\n"

    def dump(self):
        return {
            "name": self.name,
            "steps": list(self.steps),
            "entries": list(self.entries),
            "warnings": self.warnings(),
            "errors": self.errors(),
        }


class Harmonized:
    def __init__(self, frame, report, **extra):
        self.frame = frame
        self.report = report
        self.encoding = extra.get("encoding")
        self.delimiter = extra.get("delimiter")
        self.header_rows = int(extra.get("header_rows") or 0)
        self.skipped_rows = int(extra.get("skipped_rows") or 0)
        self.had_header = bool(extra.get("had_header"))
        self.column_map = dict(extra.get("column_map") or {})
        self.column_types = dict(extra.get("column_types") or {})
        self.missing = dict(extra.get("missing") or {})
        self.percent_columns = list(extra.get("percent_columns") or [])
        self.boolean_columns = list(extra.get("boolean_columns") or [])
        self.date_columns = list(extra.get("date_columns") or [])
        self.numeric_columns = list(extra.get("numeric_columns") or [])
        self.original_columns = list(extra.get("original_columns") or [])
        self.rows_in = int(extra.get("rows_in") or 0)
        self.rows_out = int(extra.get("rows_out") or 0)
        self.duplicates_removed = int(extra.get("duplicates_removed") or 0)
        self.empty_columns_removed = list(extra.get("empty_columns_removed") or [])
        self.renamed = dict(extra.get("renamed") or {})
        self.column_origin = dict(extra.get("column_origin") or {})
        self.target = extra.get("target")
        self.target_reason = extra.get("target_reason")
        self.task = extra.get("task")
        self.time = extra.get("time")
        self.group = extra.get("group")
        self.valid = bool(extra.get("valid"))
        self.problems = list(extra.get("problems") or [])
        self.notes = list(extra.get("notes") or [])

    def summary(self):
        return {
            "name": self.report.name,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "header_rows": self.header_rows,
            "skipped_rows": self.skipped_rows,
            "had_header": self.had_header,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "columns": int(self.frame.shape[1]),
            "duplicates_removed": self.duplicates_removed,
            "empty_columns_removed": self.empty_columns_removed,
            "column_types": self.column_types,
            "missing": self.missing,
            "target": self.target,
            "target_reason": self.target_reason,
            "task": self.task,
            "time": self.time,
            "group": self.group,
            "column_map": self.column_map,
            "column_origin": self.column_origin,
            "valid": self.valid,
            "problems": self.problems,
            "warnings": self.report.warnings(),
        }


def to_halfwidth(text):
    pieces = []
    for character in str(text):
        code = ord(character)
        if code == 0x3000:
            pieces.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            pieces.append(chr(code - 0xFEE0))
        else:
            pieces.append(character)
    return "".join(pieces)


def is_missing(value):
    if value is None:
        return True
    if value is pd.NaT:
        return True
    if isinstance(value, (float, np.floating)):
        return bool(math.isnan(float(value)))
    if isinstance(value, str):
        return value.strip().lower() in MISSING_MARKERS
    return False


def clean_number(value):
    if is_missing(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, (int, np.integer)):
        return float(value), {}
    if isinstance(value, (float, np.floating)):
        return float(value), {}
    if not isinstance(value, str):
        return None
    text = to_halfwidth(value).strip()
    if not text or text.lower() in MISSING_MARKERS:
        return None
    flags = {}
    for symbol in CURRENCY:
        if symbol in text:
            text = text.replace(symbol, "")
            flags["currency"] = symbol
    text = text.replace(" ", "").replace("\u00a0", "").replace("，", ",")
    if text.endswith("‰"):
        text = text[:-1]
        flags["permille"] = True
    if "%" in text:
        text = text.replace("%", "")
        flags["percent"] = True
    negative = False
    if text.startswith("(") and text.endswith(")") and len(text) > 2:
        negative = True
        text = text[1:-1].strip()
    elif text.endswith("-") and not text.startswith("-") and len(text) > 2:
        negative = True
        text = text[:-1].strip()
    matched = MAGNITUDE_PATTERN.match(text)
    if matched and matched.group(2) in MAGNITUDES:
        flags["magnitude"] = matched.group(2)
        text = matched.group(1)
    sign = ""
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        sign = "-"
        text = text[1:]
    body = text
    if body.startswith(".") and len(body) > 1:
        body = "0" + body
        flags["leading_dot"] = True
    plain = body
    if "," in body and _digit_body(body):
        plain = body.replace(",", "")
        flags["thousands"] = True
    candidate = sign + plain
    if not (
        INTEGER_PATTERN.match(candidate)
        or DECIMAL_PATTERN.match(candidate)
        or SCIENTIFIC_PATTERN.match(candidate)
    ):
        return None
    try:
        number = float(candidate)
    except ValueError:
        return None
    if flags.get("magnitude"):
        number *= MAGNITUDES[flags["magnitude"]]
    if negative:
        number = -abs(number)
    if flags.get("percent"):
        number /= 100.0
    if flags.get("permille"):
        number /= 1000.0
    return number, flags


def _digit_body(body):
    digits = False
    for character in body:
        if character.isdigit():
            digits = True
            continue
        if character in ".,":
            continue
        return False
    return digits


def _looks_numeric(value):
    if is_missing(value):
        return False
    if isinstance(value, (bool, np.bool_)):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return True
    if not isinstance(value, str):
        return False
    return clean_number(value) is not None


def _looks_date(value):
    return parse_date(value) is not None


def parse_bool(value):
    if is_missing(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return int(bool(value))
    if isinstance(value, (int, np.integer)):
        return int(value) if int(value) in (0, 1) else None
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return int(number) if number in (0.0, 1.0) else None
    if not isinstance(value, str):
        return None
    text = to_halfwidth(value).strip()
    lowered = text.lower()
    if lowered in BOOL_TRUE or text in BOOL_TRUE:
        return 1
    if lowered in BOOL_FALSE or text in BOOL_FALSE:
        return 0
    return None


def parse_date(value):
    if is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        if value.hour or value.minute or value.second:
            return value.isoformat(sep="T"), False
        return value.strftime("%Y-%m-%d"), False
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number) or not number.is_integer():
            return None
        value = str(int(number))
    elif isinstance(value, (int, np.integer)):
        value = str(int(value))
    if not isinstance(value, str):
        return None
    text = to_halfwidth(value).strip()
    if not text:
        return None
    matched = DATE_PATTERNS[4].match(text)
    if matched:
        return _iso(matched.group(1), None, None, None, None, None, False)
    matched = DATE_PATTERNS[3].match(text)
    if matched:
        return _iso(*matched.groups(), False)
    matched = DATE_PATTERNS[0].match(text)
    if matched:
        return _iso(*matched.groups(), False)
    matched = DATE_PATTERNS[2].match(text)
    if matched:
        return _iso(*matched.groups(), False)
    matched = DATE_PATTERNS[1].match(text)
    if matched:
        first, second, year, hour, minute, second_part = matched.groups()
        first_value = int(first)
        second_value = int(second)
        if first_value > 12 and second_value <= 12:
            return _iso(year, second_value, first_value, hour, minute, second_part, False)
        if second_value > 12:
            return _iso(year, first, second, hour, minute, second_part, False)
        ambiguous = (
            1 <= first_value <= 12 and 1 <= second_value <= 12 and first_value != second_value
        )
        return _iso(year, first, second, hour, minute, second_part, ambiguous)
    return None


def _iso(year, month, day, hour, minute, second, ambiguous):
    if month is None and day is None:
        return f"{int(year):04d}", ambiguous
    if month is None or day is None:
        return None
    try:
        year_value = int(year)
        month_value = int(month)
        day_value = int(day)
    except (TypeError, ValueError):
        return None
    if not (1 <= month_value <= 12) or not (1 <= day_value <= 31):
        return None
    if day_value > 28:
        try:
            pd.Timestamp(year=year_value, month=month_value, day=day_value)
        except ValueError:
            return None
    body = f"{year_value:04d}-{month_value:02d}-{day_value:02d}"
    if hour is not None and str(hour) != "":
        try:
            hour_value = int(hour)
            minute_value = int(minute) if minute not in (None, "") else 0
            second_value = int(second) if second not in (None, "") else 0
        except (TypeError, ValueError):
            return body, ambiguous
        if hour_value > 23 or minute_value > 59 or second_value > 59:
            return body, ambiguous
        body += f"T{hour_value:02d}:{minute_value:02d}:{second_value:02d}"
    return body, ambiguous


def probe_encoding(blob):
    if not isinstance(blob, (bytes, bytearray)):
        raise HarmonizeInputError("编码探测需要文件字节内容。")
    blob = bytes(blob)
    if not blob.strip():
        raise HarmonizeInputError("文件内容为空，无法探测编码，请上传非空表格。")
    if blob.startswith(codecs.BOM_UTF8):
        return {
            "encoding": "utf-8-sig",
            "text": blob.decode("utf-8-sig"),
            "score": 1.0,
            "hint": "检测到 UTF-8 BOM",
        }
    if _ascii_ratio(blob) >= 0.9 and b"\x00" not in blob:
        # Numeric-heavy tables may still have GBK headers. Never destroy those
        # bytes just because most cells are ASCII; NULs also need UTF-16 probing.
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            return {
                "encoding": "utf-8",
                "text": text,
                "score": 1.0,
                "hint": "内容以 ASCII 为主，且可无损按 UTF-8 读取",
            }
    attempts = []
    sheared = ("utf-16", "utf-16-le", "utf-16-be")
    if blob.startswith(codecs.BOM_UTF16_LE):
        attempts.append(("utf-16", 1.0, "检测到 UTF-16 小端 BOM"))
    elif blob.startswith(codecs.BOM_UTF16_BE):
        attempts.append(("utf-16", 1.0, "检测到 UTF-16 大端 BOM"))
    else:
        head = blob[:400]
        half = max(1, len(head) // 2)
        even = sum(1 for index in range(0, len(head), 2) if head[index] == 0)
        odd = sum(1 for index in range(1, len(head), 2) if head[index] == 0)
        if odd / half > 0.4 and even / half < 0.05:
            attempts.append(("utf-16-le", 0.9, "无 BOM，但零字节分布呈 UTF-16 小端特征"))
        elif even / half > 0.4 and odd / half < 0.05:
            attempts.append(("utf-16-be", 0.9, "无 BOM，但零字节分布呈 UTF-16 大端特征"))
    for encoding in ("utf-8", "gb18030", "gbk", "big5"):
        attempts.append((encoding, 0.9, None))
    attempts.append(("latin-1", 0.25, None))
    best = None
    for encoding, prior, hint in attempts:
        try:
            text = blob.decode(encoding)
        except (UnicodeDecodeError, LookupError, ValueError):
            continue
        score = _readability(text) * prior
        if encoding in sheared:
            score += 0.05
        if best is None or score > best[0]:
            best = (score, encoding, text, hint)
    if best is None:
        raise HarmonizeInputError("文件编码无法识别，请另存为 UTF-8 或 GB18030 后重试。")
    score, encoding, text, hint = best
    if score < MIN_ENCODING_SCORE:
        if _readability(text) >= 0.8 and not any(ord(character) < 9 for character in text):
            return {
                "encoding": encoding,
                "text": text,
                "score": round(_readability(text), 4),
                "hint": f"UTF-8 与 GB18030 均不能干净解码，按 {encoding} 兜底",
            }
        raise HarmonizeInputError(
            f"文件既不像 UTF-8 也不像 GB18030 文本（可读性得分 {score:.2f}），"
            "请确认这是表格文本文件，或另存为 UTF-8 后重试。"
        )
    return {"encoding": encoding, "text": text, "score": round(score, 4), "hint": hint}


def _ascii_ratio(blob):
    if not blob:
        return 1.0
    return sum(1 for byte in blob if byte < 128) / len(blob)


def _readability(text):
    sample = text[:20000]
    length = len(sample)
    if not length:
        return 0.0
    good = 0
    suspicious = 0
    for character in sample:
        if character in "\r\n\t" or character.isprintable():
            good += 1
        if (
            ord(character) >= 128
            and not ("\u4e00" <= character <= "\u9fff")
            and not ("\u3000" <= character <= "\u303f")
            and not ("\uff00" <= character <= "\uffef")
            and character not in "￥€£°²³·—–…“”‘’"
        ):
            suspicious += 1
    penalty = sample.count("\ufffd") * 6.0
    penalty += (
        sum(1 for character in sample if ord(character) < 32 and character not in "\r\n\t") * 6.0
    )
    penalty += sample.count("\x00") * 6.0
    ratio = good / length - 0.6 * (suspicious / length)
    return max(0.0, min(1.0, ratio - penalty / length))


def probe_delimiter(text):
    lines = [line for line in text.splitlines()[:SNIFF_LINES] if line.strip()]
    if not lines:
        raise HarmonizeInputError("文件里没有可解析的文本行，请确认文件不是空的。")
    best = None
    for delimiter in DELIMITERS:
        counts = _field_counts(lines, delimiter)
        score, modal = _delimiter_score(counts)
        if best is None or score > best[0]:
            best = (score, delimiter, counts, modal)
    score, delimiter, counts, modal = best
    single = _field_counts(lines, None)
    single_score, single_modal = _delimiter_score(single)
    if modal <= 1 or score <= 1.2:
        score = max(score, single_score)
        delimiter = ""
        modal = 1
    return {
        "delimiter": delimiter,
        "label": DELIMITER_LABELS.get(delimiter, delimiter),
        "score": round(float(score), 4),
        "columns": int(modal),
        "consistent": bool(all(count == modal for count in counts)),
        "counts": list(counts[:8]),
    }


def _field_counts(lines, delimiter):
    counts = []
    for line in lines:
        if delimiter == "" or delimiter is None:
            pieces = [piece for piece in SPACE_PATTERN.split(line.strip()) if piece]
        elif delimiter == " ":
            pieces = [piece for piece in re.split(r"[ \t]+", line.strip()) if piece]
        else:
            try:
                pieces = next(
                    csv.reader([line], delimiter=delimiter, quotechar='"', skipinitialspace=False)
                )
            except csv.Error:
                pieces = line.split(delimiter)
        counts.append(len(pieces))
    return counts


def _delimiter_score(counts):
    if not counts:
        return 0.0, 1
    modal = max(set(counts), key=counts.count)
    consistency = sum(1 for count in counts if count == modal) / len(counts)
    if modal <= 1:
        return consistency * 0.5, modal
    return consistency * 2.0 + (0.2 if modal >= 3 else 0.1), modal


def read_rows(text, delimiter):
    if delimiter:
        rows = []
        for row in csv.reader(io.StringIO(text), delimiter=delimiter, quotechar='"'):
            rows.append([cell.strip() for cell in row])
        return rows
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rows.append([line.strip()])
    return rows


def detect_header(rows, had_header=None):
    if not rows:
        raise HarmonizeInputError("表格里没有任何文本行，请确认文件内容。")
    width = max(len(row) for row in rows)
    rows = [list(row) + [""] * (width - len(row)) for row in rows]
    scan = min(len(rows), HEADER_SCAN_ROWS)
    skipped = 0
    while skipped < min(scan, HEADER_SEARCH_ROWS) and _preamble_like(rows[skipped]):
        skipped += 1
    if had_header is not None and skipped < scan:
        return {
            "had_header": bool(had_header),
            "skipped_rows": skipped,
            "header_rows": 1 if had_header else 0,
            "width": width,
        }
    if not rows[skipped:]:
        return {"had_header": False, "skipped_rows": skipped, "header_rows": 0, "width": width}
    if _mostly_data([rows[skipped]]):
        return {"had_header": False, "skipped_rows": skipped, "header_rows": 0, "width": width}
    if _second_row_is_data(rows, skipped):
        return {"had_header": True, "skipped_rows": skipped, "header_rows": 2, "width": width}
    return {"had_header": True, "skipped_rows": skipped, "header_rows": 1, "width": width}


def _second_row_is_data(rows, skipped):
    if len(rows) - skipped < 3:
        return False
    if not _header_like(rows[skipped + 1]):
        return False
    if not _mostly_data(rows[skipped + 2 :]):
        return False
    return not _same_kind(rows[skipped + 1], rows[skipped + 2])


def _mostly_data(rows):
    values = [cell for row in rows for cell in row if not is_missing(cell)]
    if not values:
        return False
    strong = sum(
        1
        for cell in values
        if _looks_numeric(cell) or _has_date_shape(cell) or parse_bool(cell) is not None
    )
    return strong / len(values) >= 0.5


def _blank_row(row):
    return all(not str(cell).strip() for cell in row)


def _same_kind(values, next_values):
    kinds = _kind_vector(values)
    if not any(kind is not None for kind in kinds) or not any(
        kind is not None for kind in _kind_vector(next_values)
    ):
        return False
    return kinds == _kind_vector(next_values)


def _kind_vector(values):
    kinds = []
    for value in values:
        if is_missing(value):
            kinds.append(None)
        elif _looks_numeric(value):
            kinds.append("number")
        elif _has_date_shape(value):
            kinds.append("date")
        elif parse_bool(value) is not None:
            kinds.append("boolean")
        else:
            kinds.append("text")
    return kinds


def _header_like(row):
    values = [cell for cell in row if not is_missing(cell)]
    if not values:
        return False
    if _numeric_count(values) * 3 > len(values):
        return False
    numeric = sum(1 for cell in values if _looks_numeric(cell))
    if numeric:
        return numeric * 2 < len(values)
    return any(not _looks_date(cell) for cell in values)


def _numeric_count(values):
    return sum(1 for cell in values if _looks_numeric(cell) or _has_date_shape(cell))


def _has_date_shape(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, str):
        return False
    text = to_halfwidth(value).strip()
    if not text:
        return False
    if any(symbol in text for symbol in "-/年月日") and text[0].isdigit():
        return parse_date(text) is not None
    if len(text) == 8 and text.isdigit() and text[:2] in ("19", "20"):
        return parse_date(text) is not None
    return False


def _preamble_like(row):
    values = [cell for cell in row if not is_missing(cell)]
    if not values:
        return True
    if any(isinstance(cell, str) and len(cell) >= 30 for cell in values):
        return True
    if len(values) <= 2:
        for cell in values:
            if not isinstance(cell, str):
                return False
            text = cell.strip()
            if text.endswith("：") or text.endswith(":"):
                return True
            if "：" in text or ":" in text:
                return True
            if len(text) >= 10 and not _looks_numeric(text):
                return True
        return False
    return False


def _merge_header(rows):
    width = max(len(row) for row in rows)
    names = []
    for index in range(width):
        parts = []
        for row in rows:
            cell = str(row[index]).strip() if index < len(row) else ""
            if cell and cell not in parts:
                parts.append(cell)
        names.append("_".join(parts) if parts else f"列{index + 1}")
    return names


def clean_column_names(names):
    cleaned = []
    mapping = {}
    used = {}
    for index, name in enumerate(names, start=1):
        original = "" if name is None else str(name)
        value = to_halfwidth(unicodedata.normalize("NFKC", original))
        value = CONTROL_PATTERN.sub("", value).replace("\u00a0", " ")
        value = BRACKET_PATTERN.sub("_", value)
        value = PUNCT_PATTERN.sub("_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        if not value:
            value = f"列{index}"
        lowered = value.lower()
        count = used.get(lowered, 0) + 1
        used[lowered] = count
        if count > 1:
            value = f"{value}_{count}"
        cleaned.append(value)
        mapping[value] = {"original": original, "cleaned": value, "index": index}
    return cleaned, mapping


def drop_duplicate_rows(frame):
    if frame.empty:
        return frame, 0
    keys = frame.astype("string").fillna("\x00")
    mask = keys.duplicated(keep="first")
    removed = int(mask.sum())
    return frame.loc[~mask].reset_index(drop=True), removed


def harmonize(
    source,
    name=None,
    target=None,
    time=None,
    group=None,
    dedupe=True,
    drop_empty_columns=True,
    clean_columns=True,
    drop_constant=False,
    report=None,
):
    if isinstance(source, pd.DataFrame):
        return _harmonize_frame(
            source,
            name,
            target,
            time,
            group,
            dedupe,
            drop_empty_columns,
            clean_columns,
            drop_constant,
            report,
        )
    if isinstance(source, (bytes, bytearray)):
        return _harmonize_bytes(
            bytes(source),
            name,
            target,
            time,
            group,
            dedupe,
            drop_empty_columns,
            clean_columns,
            drop_constant,
            report,
        )
    if isinstance(source, str):
        return _harmonize_text(
            source,
            name,
            target,
            time,
            group,
            dedupe,
            drop_empty_columns,
            clean_columns,
            drop_constant,
            report,
            None,
            None,
        )
    raise HarmonizeInputError("输入必须是 DataFrame、文本或文件字节内容。")


def harmonize_file(path, **options):
    path = Path(path)
    report = options.pop("report", None) or HarmonizeReport(path.name)
    if not path.is_file():
        raise HarmonizeInputError(f"找不到文件：{path}")
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES:
        raise HarmonizeInputError(
            f"不支持的文件类型 {suffix or '（无扩展名）'}，请提供 csv、tsv、txt、xlsx、xls 或 json。"
        )
    if suffix in (".xlsx", ".xlsm", ".xls"):
        try:
            frame = pd.read_excel(path, sheet_name=0)
        except ImportError as error:
            raise HarmonizeInputError(f"读取 Excel 需要 openpyxl，请先安装：{error}") from error
        except (ValueError, OSError) as error:
            raise HarmonizeInputError(f"Excel 文件读取失败：{error}") from error
        report.info(
            "文件读取",
            f"按 Excel 工作簿读取工作表 1，得到 {frame.shape[0]} 行 {frame.shape[1]} 列。",
        )
        report.info("编码探测", "Excel 是二进制格式，文本按工作簿内部 UTF-8 处理，无需探测。")
        report.info("分隔符探测", "Excel 按单元格解析，不需要分隔符。")
        report.info("表头探测", "按约定把工作表第一行当作表头。")
        return _harmonize_frame(frame, path.name, report=report, had_header=True, **options)
    blob = path.read_bytes()
    if suffix == ".json":
        payload = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                payload = json.loads(blob.decode(encoding))
                report.info("编码探测", f"JSON 按 {encoding} 解码成功，可读性良好。")
                break
            except (UnicodeDecodeError, ValueError):
                continue
        if payload is None:
            raise HarmonizeInputError("JSON 解析失败，请检查文件是否为合法 JSON 表格。")
        report.info("文件读取", "按 JSON 读取，JSON 自带结构，无需分隔符与表头探测。")
        try:
            frame = pd.DataFrame(payload)
        except ValueError as error:
            raise HarmonizeInputError(f"JSON 结构无法转成表格：{error}") from error
        return _harmonize_frame(frame, path.name, report=report, had_header=True, **options)
    return _harmonize_bytes(blob, path.name, report=report, **options)


def _harmonize_bytes(
    blob,
    name,
    target=None,
    time=None,
    group=None,
    dedupe=True,
    drop_empty_columns=True,
    clean_columns=True,
    drop_constant=False,
    report=None,
    had_header=None,
):
    report = report or HarmonizeReport(name)
    probe = probe_encoding(blob)
    hint = probe["hint"] or "多编码逐个尝试后按中文可读性打分选出"
    report.info(
        "编码探测", f"编码判定为 {probe['encoding']}，可读性得分 {probe['score']:.2f}（{hint}）。"
    )
    if probe["encoding"] in ("latin-1", "big5"):
        report.warn(
            "编码探测",
            f"UTF-8 与 GB18030 均无法干净解码，改用 {probe['encoding']} 兜底；"
            "若出现乱码请另存为 UTF-8 后重试。",
        )
    return _harmonize_text(
        probe["text"],
        name,
        target,
        time,
        group,
        dedupe,
        drop_empty_columns,
        clean_columns,
        drop_constant,
        report,
        probe["encoding"],
        None,
        had_header=had_header,
    )


def _harmonize_text(
    text,
    name,
    target=None,
    time=None,
    group=None,
    dedupe=True,
    drop_empty_columns=True,
    clean_columns=True,
    drop_constant=False,
    report=None,
    encoding=None,
    delimiter=None,
    had_header=None,
):
    report = report or HarmonizeReport(name)
    probe = probe_delimiter(text)
    report.info(
        "分隔符探测",
        f"分隔符判定为「{probe['label']}」，候选切分后列数 {probe['columns']}，"
        f"各行列数一致：{'是' if probe['consistent'] else '否'}，得分 {probe['score']:.2f}。",
    )
    if probe["columns"] <= 1:
        report.info("分隔符探测", "逗号、制表符、分号、竖线、空格都无法切出多列，按单列表格处理。")
    rows = read_rows(text, probe["delimiter"])
    if not rows:
        report.error("文件读取", "文件里没有任何非空文本行，请确认文件内容。")
        raise HarmonizeInputError(f"{name or '输入'}没有任何非空文本行，请确认文件内容。")
    header = detect_header(rows, had_header=had_header)
    if header["had_header"]:
        extra = f"，表头占 {header['header_rows']} 行" if header["header_rows"] > 1 else ""
        report.info(
            "表头探测", f"判定：有表头；表头之前有 {header['skipped_rows']} 行说明文字{extra}。"
        )
    else:
        report.info("表头探测", "判定：无表头（第一行即数据，后续行以数值为主），列名自动生成。")
    start = header["skipped_rows"]
    for offset in range(start):
        preview = " | ".join(cell for cell in rows[offset] if cell)
        report.info("表头探测", f"跳过说明文字第 {offset + 1} 行：{preview[:100]}。")
    header_names = None
    if header["had_header"]:
        header_names = _merge_header(
            [rows[start + offset] for offset in range(header["header_rows"])]
        )
        for offset in range(header["header_rows"]):
            preview = " | ".join(cell for cell in rows[start + offset] if cell)
            report.info("表头探测", f"表头第 {offset + 1} 行原文：{preview[:120]}。")
        start += header["header_rows"]
    body = [row for row in rows[start:] if not _blank_row(row)]
    if not body:
        report.error("表头探测", "跳过表头后没有数据行，请确认表头判定是否正确。")
        raise HarmonizeInputError(f"{name or '输入'}在表头之后没有数据行，请确认表头识别是否正确。")
    width = max(len(row) for row in body)
    if header_names is None:
        header_names = [f"列{index + 1}" for index in range(width)]
    if len(header_names) < width:
        header_names = list(header_names) + [
            f"列{index + 1}" for index in range(len(header_names), width)
        ]
    body = [
        list(row)[: len(header_names)] + [""] * max(0, len(header_names) - len(row)) for row in body
    ]
    frame = pd.DataFrame(body, columns=list(range(len(header_names))))
    return _harmonize_frame(
        frame,
        name,
        target,
        time,
        group,
        dedupe,
        drop_empty_columns,
        clean_columns,
        drop_constant,
        report,
        encoding,
        probe["delimiter"],
        header_names=header_names,
        header=header,
        rows_in=len(body),
    )


def _harmonize_frame(
    frame,
    name,
    target=None,
    time=None,
    group=None,
    dedupe=True,
    drop_empty_columns=True,
    clean_columns=True,
    drop_constant=False,
    report=None,
    encoding=None,
    delimiter=None,
    header_names=None,
    header=None,
    rows_in=None,
    had_header=None,
):
    report = report or HarmonizeReport(name)
    if not isinstance(frame, pd.DataFrame):
        raise HarmonizeInputError("内部错误：期望 DataFrame。")
    if frame.shape[1] == 0:
        report.error("表格概况", "表格没有任何列，请确认分隔符与表头识别结果。")
        raise HarmonizeInputError(f"{name or '输入'}解析后没有任何列，请确认分隔符与表头是否正确。")
    original_columns = [str(value) for value in frame.columns]
    report.info(
        "表格概况",
        f"解析得到 {frame.shape[0]} 行 {frame.shape[1]} 列，原始列名："
        + "、".join(original_columns[:12])
        + ("…" if len(original_columns) > 12 else ""),
    )
    frame = frame.copy()
    if header_names is not None:
        frame.columns = list(header_names)
    frame = frame.map(_strip_value)
    frame = frame.replace({"": None})
    original_columns = [str(value) for value in frame.columns]

    seen_names = {}
    unique_names = []
    duplicate_positions = []
    for position, value in enumerate(frame.columns):
        text = str(value)
        seen_names[text] = seen_names.get(text, 0) + 1
        if seen_names[text] > 1:
            duplicate_positions.append((position, text, seen_names[text]))
            unique_names.append(f"{text}_{seen_names[text]}")
        else:
            unique_names.append(value)
    if duplicate_positions:
        frame.columns = unique_names
        detail = "、".join(
            f"第 {position + 1} 列「{text}」→ {text}_{count}"
            for position, text, count in duplicate_positions
        )
        report.info(
            "重名列处理",
            f"发现 {len(duplicate_positions)} 个重复列名，自动加序号后缀：" + detail + "。",
        )
    column_origin = {str(value): str(value) for value in frame.columns}

    empty_columns = [str(value) for value in frame.columns if frame[value].map(is_missing).all()]
    if empty_columns and drop_empty_columns:
        frame = frame.drop(
            columns=[value for value in frame.columns if str(value) in empty_columns]
        )
        column_origin = {str(value): str(value) for value in frame.columns}
        report.info(
            "全空列处理", f"删除 {len(empty_columns)} 个全空列：{'、'.join(empty_columns)}。"
        )
    elif empty_columns:
        report.warn(
            "全空列处理",
            f"发现 {len(empty_columns)} 个全空列，按配置保留：{'、'.join(empty_columns)}。",
        )
    duplicates_raw = sorted(
        {value for value in original_columns if original_columns.count(value) > 1}
    )

    if clean_columns or header_names is not None:
        cleaned, mapping = clean_column_names(list(frame.columns))
        column_map = mapping
        frame.columns = cleaned
        column_origin = {
            str(entry["cleaned"]): column_origin.get(str(entry["original"]), str(entry["original"]))
            for entry in mapping.values()
        }
        changed = [
            f"{entry['original']} → {entry['cleaned']}"
            for entry in mapping.values()
            if entry["original"] != entry["cleaned"]
        ]
        if changed:
            report.info(
                "列名统一",
                f"规整 {len(changed)} 个列名（去空白与不可见字符、全角转半角、"
                "括号与空格归一化为下划线、大小写风格统一、重名加后缀）："
                + "；".join(changed[:20])
                + ("…" if len(changed) > 20 else "。"),
            )
        else:
            report.info("列名统一", "列名已经符合规范，无需修改。")
        if duplicates_raw and not duplicate_positions:
            report.info("重名列处理", "重名列自动加序号后缀：" + "、".join(duplicates_raw) + "。")
    else:
        column_map = {
            str(value): {"original": str(value), "cleaned": str(value), "index": index + 1}
            for index, value in enumerate(frame.columns)
        }

    for value in frame.columns:
        values = frame[value].tolist()
        count = sum(1 for item in values if is_missing(item))
        report.info(
            "缺失值统计", f"列 {value} 缺失 {count} 个，占比 {count / max(1, len(values)):.1%}。"
        )

    column_types = {}
    numeric_columns = []
    boolean_columns = []
    date_columns = []
    percent_columns = []
    notes = []
    conversions = {}
    for value in frame.columns:
        series = frame[value]
        values = series.tolist()
        missing_before = sum(1 for item in values if is_missing(item))
        present = [item for item in values if not is_missing(item)]
        if pd.api.types.is_bool_dtype(series):
            converted = series.astype("int64")
            conversions[value] = converted
            column_types[str(value)] = "boolean"
            boolean_columns.append(str(value))
            report.info(
                "布尔列统一",
                f"列 {value} 本就是布尔型，统一为 0/1，真值 {int(converted.sum())} 个。",
            )
        elif pd.api.types.is_numeric_dtype(series):
            conversions[value] = pd.to_numeric(series, errors="coerce")
            column_types[str(value)] = "number"
            numeric_columns.append(str(value))
            report.info("数值列统一", f"列 {value} 已是数值型，保留 {len(present)} 个有效值。")
        elif not present:
            column_types[str(value)] = "empty"
        else:
            numeric_hits = [item for item in present if _looks_numeric(item)]
            boolean_hits = [item for item in present if parse_bool(item) is not None]
            date_hits = [item for item in present if parse_date(item) is not None]
            if len(numeric_hits) / len(present) >= TYPE_COVERAGE and _numeric_worthy(present):
                converted, flags, failures = _convert_numeric(values)
                conversions[value] = converted
                column_types[str(value)] = "number"
                numeric_columns.append(str(value))
                summary = _flag_summary(flags)
                report.info(
                    "数值列统一",
                    f"列 {value} 由文本转数值：{len(numeric_hits)}/{len(present)} 个值可解析"
                    + (f"；{summary}。" if summary else "，无需特殊处理。"),
                )
                if failures:
                    report.info(
                        "数值列统一",
                        f"列 {value} 有 {len(failures)} 个值无法解析为数值，已标为缺失："
                        + "、".join(failures[:5])
                        + ("…" if len(failures) > 5 else "。"),
                    )
                percent_count = sum(1 for flag in flags if flag.get("percent"))
                if percent_count:
                    percent_columns.append(str(value))
                    report.info(
                        "数值列统一",
                        f"列 {value} 有 {percent_count} 个百分号数值，已转成小数（12% → 0.12）。",
                    )
            elif _boolean_worthy(present, boolean_hits):
                converted = pd.Series([parse_bool(item) for item in values], dtype="float64")
                conversions[value] = converted
                column_types[str(value)] = "boolean"
                boolean_columns.append(str(value))
                samples = "、".join(
                    f"{item}→{parse_bool(item)}" for item in list(dict.fromkeys(present))[:4]
                )
                report.info(
                    "布尔列统一",
                    f"列 {value} 识别为布尔列，{len(set(str(item) for item in present))} 种原值"
                    f"统一为 0/1（真值 {int(converted.fillna(0).sum())} 个）：{samples}。",
                )
            elif len(date_hits) / len(present) >= TYPE_COVERAGE:
                converted, ambiguous = _convert_date(values)
                conversions[value] = converted
                column_types[str(value)] = "date"
                date_columns.append(str(value))
                samples = "、".join(f"{item} → {parse_date(item)[0]}" for item in present[:3])
                report.info(
                    "日期列统一", f"列 {value} 识别为日期列，统一成 ISO 字符串：{samples}。"
                )
                raw_name = f"{value}{RAW_SUFFIX}"
                frame[raw_name] = pd.Series(values, index=frame.index)
                notes.append(f"列 {value} 的原始值保留在 {raw_name} 供核对。")
                report.info("日期列统一", f"原始值保留在派生列 {raw_name}，可逐行核对。")
                if ambiguous:
                    report.warn(
                        "日期列统一",
                        f"列 {value} 有 {len(ambiguous)} 个歧义日期（月、日都 ≤12，例如 "
                        + "、".join(ambiguous[:3])
                        + "），已按「月/日/年」解析，请人工确认。",
                    )
            else:
                column_types[str(value)] = "text"
                report.info(
                    "列类型判定",
                    f"列 {value} 保留为文本列，{len(present)} 个有效值、"
                    f"{len(set(str(item) for item in present))} 种取值。",
                )
        missing_after = sum(1 for item in values if is_missing(item))
        if (
            column_types[str(value)] in ("number", "boolean", "date")
            and missing_after != missing_before
        ):
            report.info(
                "缺失值统计", f"列 {value} 统一后新增 {missing_after - missing_before} 个缺失标记。"
            )
    for value, converted in conversions.items():
        frame[value] = converted

    if drop_constant:
        constants = [
            value
            for value in frame.columns
            if frame[value].nunique(dropna=True) <= 1 and not str(value).endswith(RAW_SUFFIX)
        ]
        if constants:
            frame = frame.drop(columns=constants)
            report.info(
                "常量列处理",
                f"删除 {len(constants)} 个常量列：{'、'.join(str(value) for value in constants)}。",
            )

    duplicates_removed = 0
    if dedupe:
        frame, duplicates_removed = drop_duplicate_rows(frame)
        if duplicates_removed:
            report.info("重复行处理", f"删除完全重复的行 {duplicates_removed} 行，只保留首次出现。")
        else:
            report.info("重复行处理", "没有发现完全重复的行。")

    target_name, target_reason = infer_target(frame, explicit=target)
    if target and target_name not in frame.columns:
        available = "、".join(str(value) for value in frame.columns[:12])
        report.error("目标列推断", f"指定的目标列 {target} 不在统一后的列中，可用列：{available}。")
        raise HarmonizeInputError(f"目标列 {target} 不在统一后的列中，可用列：{available}")
    report.info("目标列推断", f"目标列为 {target_name}，依据：{target_reason}。")
    task = infer_task(frame[target_name] if target_name in frame.columns else None)
    report.info(
        "任务类型推断",
        f"任务类型判定为{_task_label(task)}，依据："
        + {
            "clustering": "目标列缺失，按聚类处理",
            "classification": "目标列取值有限且都是整数，按分类处理",
            "regression": "目标列取值连续，按回归处理",
        }.get(task, "按默认处理")
        + "。",
    )
    for role, chosen in (("时间", time), ("分组", group)):
        if chosen and chosen not in frame.columns:
            available = "、".join(str(value) for value in frame.columns[:12])
            report.error("角色列校验", f"{role}列 {chosen} 不在统一后的列中，可用列：{available}。")
            raise HarmonizeInputError(f"{role}列 {chosen} 不在统一后的列中，可用列：{available}")

    problems = validate_frame(frame, column_types)
    if problems:
        for problem in problems:
            report.error("一致性校验", problem)
    else:
        report.info(
            "一致性校验",
            f"通过：{frame.shape[0]} 行 {frame.shape[1]} 列，列数一致、无全空列、每列类型明确。",
        )

    missing_report = {}
    for value in frame.columns:
        values = frame[value].tolist()
        count = sum(1 for item in values if is_missing(item))
        missing_report[str(value)] = {
            "count": count,
            "ratio": round(count / max(1, len(values)), 4),
        }
    total_in = int(rows_in if rows_in is not None else frame.shape[0] + duplicates_removed)
    return Harmonized(
        frame,
        report,
        encoding=encoding,
        delimiter=delimiter,
        header_rows=(header or {}).get("header_rows", 0),
        skipped_rows=(header or {}).get("skipped_rows", 0),
        had_header=bool(
            (header or {}).get("had_header", had_header if had_header is not None else True)
        ),
        column_map=column_map,
        column_types=column_types,
        missing=missing_report,
        column_origin=column_origin,
        percent_columns=percent_columns,
        boolean_columns=boolean_columns,
        date_columns=date_columns,
        numeric_columns=numeric_columns,
        original_columns=original_columns,
        rows_in=total_in,
        rows_out=int(frame.shape[0]),
        duplicates_removed=duplicates_removed,
        empty_columns_removed=empty_columns,
        renamed={
            entry["original"]: entry["cleaned"]
            for entry in column_map.values()
            if entry["original"] != entry["cleaned"]
        },
        target=target_name,
        target_reason=target_reason,
        task=task,
        time=time,
        group=group,
        valid=not problems,
        problems=problems,
        notes=notes,
    )


def _value_key(value):
    if value is None:
        return ("none",)
    if isinstance(value, float) and math.isnan(value):
        return ("nan",)
    return (type(value).__name__, str(value))


def _strip_value(value):
    return value.strip() if isinstance(value, str) else value


def _convert_numeric(values):
    mapped = {}
    flags = []
    failures = []
    for value in values:
        if is_missing(value):
            continue
        outcome = clean_number(value)
        if outcome is None:
            failures.append(str(value))
            continue
        number, flag = outcome
        mapped[_value_key(value)] = number
        if flag:
            flags.append(flag)
    series = pd.Series([mapped.get(_value_key(value)) for value in values], dtype="float64")
    return series, flags, failures


def _convert_date(values):
    mapped = {}
    ambiguous = []
    for value in values:
        if is_missing(value):
            continue
        outcome = parse_date(value)
        if outcome is None:
            continue
        text, is_ambiguous = outcome
        mapped[_value_key(value)] = text
        if is_ambiguous:
            ambiguous.append(str(value))
    series = pd.Series([mapped.get(_value_key(value)) for value in values], dtype="object")
    return series, ambiguous


def _flag_summary(flags):
    seen = {}
    for flag in flags:
        for key, value in flag.items():
            seen.setdefault(key, set()).add(value if isinstance(value, str) else "")
    parts = []
    if "thousands" in seen:
        parts.append("去掉千分位逗号")
    if "currency" in seen:
        symbols = "".join(sorted(symbol for symbol in seen["currency"] if symbol))
        parts.append(f"去掉货币符号 {symbols}")
    if "percent" in seen:
        parts.append("百分号转小数")
    if "permille" in seen:
        parts.append("千分号转小数")
    if "magnitude" in seen:
        parts.append(
            "中文数量级换算：" + "、".join(sorted(value for value in seen["magnitude"] if value))
        )
    if "leading_dot" in seen:
        parts.append("补全小数前导零")
    return "；".join(parts)


def _numeric_worthy(present):
    if len(present) <= 3:
        return True
    return not any(any(word in str(value) for word in NUMERIC_STOPWORDS) for value in present[:8])


def _boolean_worthy(present, boolean_hits):
    if len(set(str(value) for value in present)) > 8:
        return False
    return len(boolean_hits) == len(present)


def validate_frame(frame, column_types=None):
    problems = []
    if frame is None or not isinstance(frame, pd.DataFrame):
        return ["统一结果不是表格对象，请检查输入。"]
    if frame.shape[0] <= 0:
        problems.append("统一后行数为 0：所有行都被判为说明文字或重复行，请检查表头与去重设置。")
    if frame.shape[1] <= 0:
        problems.append("统一后没有任何列：请检查分隔符与表头是否识别正确。")
    widths = {len(frame[value].tolist()) for value in frame.columns}
    if len(widths) > 1:
        problems.append("各列长度不一致：存在错位行，请检查文件是否有未闭合的引号或多余分隔符。")
    for value in frame.columns:
        if frame[value].map(is_missing).all():
            problems.append(f"列 {value} 全为空：请在源文件中补齐该列，或确认该列不应存在。")
    if column_types:
        unknown = [str(name) for name, kind in column_types.items() if kind not in COLUMN_TYPES]
        if unknown:
            problems.append("以下列无法确定类型：" + "、".join(unknown) + "，请检查取值是否混杂。")
    return problems


def infer_target(frame, explicit=None):
    if explicit:
        if explicit in frame.columns:
            return explicit, "调用方显式指定"
        lowered = {str(name).lower(): name for name in frame.columns}
        if isinstance(explicit, str) and explicit.lower() in lowered:
            return lowered[explicit.lower()], "调用方显式指定（忽略大小写匹配）"
        return explicit, "调用方显式指定（统一后未出现该列）"
    candidates = [name for name in frame.columns if not str(name).endswith(RAW_SUFFIX)]
    lowered = {str(name).strip().lower(): name for name in candidates}
    for candidate in TARGET_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate], f"列名命中平台候选词「{candidate}」"
    if candidates:
        return candidates[-1], "未命中候选词，按平台默认取最后一列"
    if len(frame.columns):
        return frame.columns[-1], "只有日期原始值列，按最后一列推断"
    return None, "表格没有任何列"


def infer_task(target):
    if target is None:
        return "clustering"
    series = pd.Series(target)
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce").dropna()
    else:
        values = [value for value in series.tolist() if not is_missing(value)]
        if not values:
            return "clustering"
        if sum(1 for value in values if _looks_numeric(value)) / len(values) < TYPE_COVERAGE:
            return "classification"
        numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    unique = pd.unique(numeric)
    if len(unique) == 0:
        return "clustering"
    if 2 <= len(unique) <= 10 and all(float(value).is_integer() for value in unique):
        return "classification"
    return "regression"


def _task_label(task):
    return {"classification": "分类", "regression": "回归", "clustering": "聚类"}.get(
        task, str(task)
    )


def write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def output_path(source, out_dir, suffix="_harmonized"):
    return Path(out_dir) / f"{Path(source).stem}{suffix}.csv"


class Harmonizer:
    def __init__(
        self,
        name=None,
        target=None,
        time=None,
        group=None,
        dedupe=True,
        drop_empty_columns=True,
        clean_columns=True,
        drop_constant=False,
    ):
        self.name = name
        self.target = target
        self.time = time
        self.group = group
        self.dedupe = dedupe
        self.drop_empty_columns = drop_empty_columns
        self.clean_columns = clean_columns
        self.drop_constant = drop_constant

    def run(self, source, name=None):
        report = HarmonizeReport(name or self.name)
        return harmonize(
            source,
            name=name or self.name,
            target=self.target,
            time=self.time,
            group=self.group,
            dedupe=self.dedupe,
            drop_empty_columns=self.drop_empty_columns,
            clean_columns=self.clean_columns,
            drop_constant=self.drop_constant,
            report=report,
        )

    def run_file(self, path):
        return harmonize_file(
            path,
            target=self.target,
            time=self.time,
            group=self.group,
            dedupe=self.dedupe,
            drop_empty_columns=self.drop_empty_columns,
            clean_columns=self.clean_columns,
            drop_constant=self.drop_constant,
        )

    def run_many(self, path):
        return [self.run_file(item) for item in collect_inputs(path)]


def collect_inputs(path):
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise HarmonizeInputError(f"找不到输入路径：{path}")
    files = sorted(
        child for child in path.iterdir() if child.is_file() and child.suffix.lower() in SUFFIXES
    )
    if not files:
        raise HarmonizeInputError(f"目录 {path} 里没有 csv、tsv、txt、xlsx、xls 或 json 文件。")
    return files


def standard_payload(frame):
    columns = [str(name) for name in frame.columns]
    head = []
    for index in range(min(5, frame.shape[0])):
        head.append({name: _json_safe(frame[name].iloc[index]) for name in columns})
    return {
        "columns": columns,
        "rows": int(frame.shape[0]),
        "dtypes": {str(name): str(frame[name].dtype) for name in frame.columns},
        "head": head,
    }


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) else round(number, 6)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
