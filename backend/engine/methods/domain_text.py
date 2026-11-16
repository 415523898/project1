"""Existing domain text algorithms; registered by engine.methods.domain."""

import re

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, table_of

STOPWORDS = frozenset(
    [
        "的",
        "了",
        "和",
        "是",
        "在",
        "有",
        "我",
        "你",
        "他",
        "她",
        "它",
        "们",
        "这",
        "那",
        "个",
        "就",
        "都",
        "也",
        "还",
        "很",
        "太",
        "不",
        "没",
        "把",
        "被",
        "让",
        "给",
        "对",
        "从",
        "到",
        "与",
        "及",
        "而",
        "或",
        "但",
        "却",
        "则",
        "之",
        "其",
        "为",
        "以",
        "于",
        "上",
        "下",
        "里",
        "些",
        "么",
        "呢",
        "吗",
        "吧",
        "啊",
        "一个",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "什么",
        "因为",
        "所以",
        "如果",
        "但是",
        "而且",
        "就是",
        "可以",
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "this",
        "that",
        "with",
        "as",
        "at",
        "by",
        "from",
        "we",
        "you",
        "they",
        "he",
        "she",
        "not",
        "no",
        "but",
        "if",
        "then",
        "so",
        "will",
        "can",
        "do",
        "does",
        "did",
        "has",
        "have",
        "had",
        "our",
        "their",
        "its",
        "there",
        "which",
    ]
)


NEGATIONS = ("不", "没", "无", "非", "未", "别", "勿", "莫")


def _tokenize(document):
    return [part for part in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", str(document).lower()) if part]


def _word_analyzer(document):
    return _tokenize(document)


def _clean_analyzer(document):
    return [token for token in _tokenize(document) if len(token) > 1 and token not in STOPWORDS]


def _length_analyzer(minimum):
    def analyze(document):
        return [token for token in _tokenize(document) if len(token) >= int(minimum)]

    return analyze


def _stopword_analyzer(minimum):
    def analyze(document):
        return [
            token
            for token in _tokenize(document)
            if len(token) >= int(minimum) and token not in STOPWORDS
        ]

    return analyze


def _ngram_analyzer(ngram_max):
    def analyze(document):
        tokens = _tokenize(document)
        result = list(tokens)
        for size in range(2, int(ngram_max) + 1):
            result.extend(
                " ".join(tokens[position : position + size])
                for position in range(len(tokens) - size + 1)
            )
        return result

    return analyze


def _phrase_analyzer(analyze, ngram_max):
    if int(ngram_max) <= 1:
        return analyze

    def combined(document):
        tokens = analyze(document)
        result = list(tokens)
        for size in range(2, int(ngram_max) + 1):
            result.extend(
                " ".join(tokens[position : position + size])
                for position in range(len(tokens) - size + 1)
            )
        return result

    return combined


def _text_column(context):
    table = context.table
    name = context.text("text_column") or table.group_name or table.time_name
    if not name or name not in table.raw.columns:
        for candidate in table.raw.columns:
            if candidate == table.target_name:
                continue
            if table.raw[candidate].dtype == object or str(table.raw[candidate].dtype).startswith(
                "str"
            ):
                name = candidate
                break
    if not name or name not in table.raw.columns:
        raise MethodError("需要一个文本列，可用 text_column 指定。")
    documents = table.raw[name].astype("string").fillna("").tolist()
    if not any(document.strip() for document in documents):
        raise MethodError(f"列 {name} 没有可分析的文本。")
    return name, documents


def wordfreq(context):
    from sklearn.feature_extraction.text import CountVectorizer

    name, documents = _text_column(context)
    top = context.whole("top", 30, 5, 200)
    minimum = context.whole("min_df", 1, 1, 100)
    max_features = context.whole("max_features", None, 5, 100000)
    clean = context.flag("clean_stopwords", True)
    min_length = context.whole("min_length", 2, 1, 10)
    ngram_max = context.whole("ngram_max", 1, 1, 3)
    bar_plot = context.flag("bar_plot", True)
    token_analyzer = _stopword_analyzer(min_length) if clean else _length_analyzer(min_length)
    analyzer = _phrase_analyzer(token_analyzer, ngram_max)
    vectorizer = CountVectorizer(min_df=minimum, max_features=max_features, analyzer=analyzer)
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError as error:
        raise MethodError(
            f"无法切分文本：{error}。当前词元最小长度 {min_length}、"
            f"最少出现文档数 {minimum}，可调低这两个参数或关闭停用词过滤。"
        ) from error
    counts = np.asarray(matrix.sum(axis=0)).ravel()
    terms = vectorizer.get_feature_names_out()
    candidates = {token for document in documents for token in _word_analyzer(document)}
    kept = {token for document in documents for token in token_analyzer(document)}
    filtered = max(len(candidates) - len(kept), 0)
    order = np.argsort(-counts)
    rows = pd.DataFrame(
        {
            "term": [str(terms[index]) for index in order[:top]],
            "count": counts[order[:top]].astype(int),
            "share": numbers(counts[order[:top]] / max(counts.sum(), 1), 6),
        }
    )
    length = pd.Series([len(document) for document in documents])
    notes = [
        "分词默认按空格与标点切分，中文需要预先分词或使用字符级 min_df。",
        "词频高不代表重要，重要词要看 TF-IDF 或主题模型。",
    ]
    if clean:
        notes.append(f"已按内置中英文停用词表去掉单字与停用词，本次影响 {filtered} 个词元。")
    if min_length != 2:
        notes.append(f"词元最小长度设为 {min_length}，短于该长度的词元不参与统计。")
    if ngram_max > 1:
        notes.append(f"已把相邻词合并成最多 {ngram_max} 个词的词组一起统计。")
    if max_features is not None:
        notes.append(f"词表只保留出现总次数最多的 {int(max_features)} 个词元。")
    if bar_plot:
        try:
            import matplotlib.pyplot as plt

            chart = rows.head(min(int(rows.shape[0]), 20))
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.barh(
                [str(term) for term in chart["term"]][::-1],
                chart["count"].to_numpy()[::-1],
                color="#4f7cff",
            )
            axis.set_xlabel("出现次数")
            axis.set_title(f"词频前 {int(chart.shape[0])} 个词元")
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_wordfreq_top")
        except ImportError:
            context.warn("未安装 matplotlib，跳过词频条形图。")
    return registry.result(
        "domain.wordfreq",
        context.table,
        metrics={
            "text_column": name,
            "documents": len(documents),
            "vocabulary": int(len(terms)),
            "total_tokens": int(counts.sum()),
            "mean_length": round(float(length.mean()), 2),
            "clean_stopwords": bool(clean),
            "min_length": int(min_length),
            "ngram_max": int(ngram_max),
            "filtered_terms": int(filtered),
            "top_term": str(terms[int(order[0])]) if len(order) else None,
        },
        tables={"top_terms": table_of(rows, limit=top)},
        notes=notes,
    )


def tfidf(context):
    from sklearn.feature_extraction.text import TfidfVectorizer

    name, documents = _text_column(context)
    top = context.whole("top", 30, 5, 200)
    ngram_max = context.whole("ngram_max", 1, 1, 3)
    min_df = context.whole("min_df", 1, 1, 100)
    min_length = context.whole("min_length", 1, 1, 10)
    max_features = context.whole("max_features", None, 5, 100000)
    max_df = context.number("max_df", 1.0, 0.1, 1.0)
    sublinear = context.flag("sublinear_tf", False)
    smooth = context.flag("smooth_idf", True)
    bar_plot = context.flag("bar_plot", True)
    norm = context.text("norm", "l2", ("l2", "l1", "none"))
    cutoff = int(max_df * len(documents))
    analyzer = _phrase_analyzer(_length_analyzer(min_length), ngram_max)
    vectorizer = TfidfVectorizer(
        min_df=min_df,
        max_df=max_df,
        max_features=max_features,
        analyzer=analyzer,
        sublinear_tf=sublinear,
        smooth_idf=smooth,
        norm=None if norm == "none" else norm,
    )
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError as error:
        raise MethodError(
            f"无法切分文本：{error}。最高文档频率 {max_df:g} 过滤后没有剩余词。"
        ) from error
    terms = vectorizer.get_feature_names_out()
    scores = np.asarray(matrix.mean(axis=0)).ravel()
    order = np.argsort(-scores)
    rows = pd.DataFrame(
        {
            "term": [str(terms[index]) for index in order[:top]],
            "mean_tfidf": numbers(scores[order[:top]], 6),
            "document_count": np.asarray((matrix > 0).sum(axis=0)).ravel()[order[:top]].astype(int),
        }
    )
    notes = [
        "TF-IDF 用词频乘以逆文档频率，压制在所有文档中都出现的常见词。",
        f"词组最长 {ngram_max} 个词，文档频率超过 {max_df:g} 的词被丢弃（本次阈值 {cutoff} 篇）。",
        "文档-词矩阵默认只展示前 10 行与前 12 列。",
    ]
    if sublinear:
        notes.append("已对词频取对数（sublinear tf），削弱高频词的主导作用。")
    if norm != "l2":
        notes.append(f"向量归一化方式为 {norm}，会改变每个词的 TF-IDF 量级。")
    if min_df > 1:
        notes.append(f"词表只保留出现在至少 {min_df} 篇文档中的词。")
    if min_length > 1:
        notes.append(f"短于 {min_length} 个字符的词元不参与统计。")
    if max_features is not None:
        notes.append(f"词表最多保留权重最高的 {int(max_features)} 个词。")
    if not smooth:
        notes.append("已关闭 IDF 平滑，所有文档都出现的词权重会退化为 0。")
    if bar_plot:
        try:
            import matplotlib.pyplot as plt

            chart = rows.head(min(int(rows.shape[0]), 20))
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.barh(
                [str(term) for term in chart["term"]][::-1],
                chart["mean_tfidf"].to_numpy()[::-1],
                color="#4f7cff",
            )
            axis.set_xlabel("平均 TF-IDF 权重")
            axis.set_title(f"TF-IDF 权重前 {int(chart.shape[0])} 个关键词")
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_tfidf_top")
        except ImportError:
            context.warn("未安装 matplotlib，跳过关键词条形图。")
    return registry.result(
        "domain.tfidf",
        context.table,
        metrics={
            "text_column": name,
            "documents": int(matrix.shape[0]),
            "vocabulary": int(matrix.shape[1]),
            "mean_nonzero": round(float(matrix.nnz / max(matrix.shape[0], 1)), 4),
            "ngram_max": ngram_max,
            "max_df": round(float(max_df), 6),
            "sublinear_tf": bool(sublinear),
            "norm": norm,
            "max_df_cut": min(cutoff, len(documents)),
            "top_term": str(terms[int(order[0])]) if len(order) else None,
        },
        tables={
            "top_terms": table_of(rows, limit=top),
            "document_matrix": table_of(
                pd.DataFrame(
                    matrix.toarray()[:10, : min(12, matrix.shape[1])],
                    columns=[str(term) for term in terms[: min(12, matrix.shape[1])]],
                ),
                limit=10,
            ),
        },
        notes=notes,
    )


def _sentiment_hits(text, positive, negative, window):
    good = 0
    bad = 0
    flipped = 0
    for words, sign in ((positive, 1), (negative, -1)):
        for word in words:
            position = text.find(word)
            if position < 0:
                continue
            head = text[max(0, position - int(window)) : position]
            polarity = sign
            if any(item in head for item in NEGATIONS):
                polarity = -sign
                flipped += 1
            if polarity > 0:
                good += 1
            else:
                bad += 1
    return good, bad, flipped


def sentiment(context):
    positive = set(context.text("positive_words", "").replace("，", ",").split(","))
    negative = set(context.text("negative_words", "").replace("，", ",").split(","))
    positive = {word.strip() for word in positive if word.strip()}
    negative = {word.strip() for word in negative if word.strip()}
    if not positive and not negative:
        positive = {"好", "很好", "满意", "喜欢", "推荐", "优秀", "快", "值得", "赞", "棒"}
        negative = {"差", "很差", "不满意", "失望", "贵", "慢", "退货", "垃圾", "糟糕", "问题"}
        context.warn("未提供情感词典，已使用内置的通用中文词典。")

    name, documents = _text_column(context)
    top_terms = context.whole("top_terms", 15, 3, 60)
    min_length = context.whole("min_length", 1, 1, 10)
    negation_window = context.whole("negation_window", 0, 0, 8)
    detail_rows = context.whole("detail_rows", 40, 5, 200)
    group_column = context.text("group_column")
    distribution_plot = context.flag("distribution_plot", True)
    polarity_plot = context.flag("polarity_plot", True)
    scores = []
    labels = []
    hits = []
    flipped_total = 0
    for document in documents:
        text = str(document)
        if negation_window > 0:
            good, bad, flipped = _sentiment_hits(text, positive, negative, negation_window)
            flipped_total += flipped
        else:
            good = sum(1 for word in positive if word in text)
            bad = sum(1 for word in negative if word in text)
        total = good + bad
        score = (good - bad) / total if total else 0.0
        scores.append(score)
        labels.append("正面" if score > 0 else "负面" if score < 0 else "中性")
        hits.append(good - bad)
    scores = np.asarray(scores, dtype=float)
    distribution = pd.Series(labels).value_counts()
    rows = pd.DataFrame(
        {
            "label": distribution.index,
            "count": distribution.to_numpy(),
            "ratio": numbers(distribution.to_numpy() / max(len(labels), 1), 4),
        }
    )
    detail = pd.DataFrame(
        {
            "document": [str(document)[:60] for document in documents[:detail_rows]],
            "score": numbers(scores[:detail_rows], 4),
            "label": labels[:detail_rows],
            "hits": hits[:detail_rows],
        }
    )
    counter = pd.Series(
        [
            token
            for document in documents
            for token in _word_analyzer(document)
            if len(token) >= min_length
        ]
    )
    if counter.empty:
        raise MethodError("文本切分后没有得到任何词，无法列出代表词。")
    counts = counter.value_counts()
    term_rows = pd.DataFrame(
        {
            "term": [str(term) for term in counts.index[:top_terms]],
            "count": counts.to_numpy()[:top_terms],
            "share": numbers(counts.to_numpy()[:top_terms] / max(int(counts.sum()), 1), 6),
        }
    )
    tables = {
        "distribution": table_of(rows),
        "documents": table_of(detail, limit=detail_rows),
        "top_terms": table_of(term_rows, limit=top_terms),
    }
    notes = [
        "这是词典法情感打分，只统计词典命中数之差，不理解上下文与否定。",
        "可以传入 positive_words / negative_words 覆盖默认词典。",
        f"代表词表按出现次数排序，最多列出 {top_terms} 个词。",
    ]
    if negation_window > 0:
        notes.append(
            f"已启用否定词处理：情感词前 {negation_window} 个字符内出现否定词时极性翻转，"
            f"本次共翻转 {flipped_total} 个情感词命中。"
        )
    if min_length > 1:
        notes.append(f"代表词表只统计长度不少于 {min_length} 个字符的词元。")
    if group_column:
        if group_column not in context.table.raw.columns:
            raise MethodError(
                f"分组列 {group_column} 不在数据中。"
                f"可选：{'、'.join(str(name) for name in context.table.raw.columns[:12])}"
            )
        group_labels = context.table.raw[group_column].astype("string").fillna("缺失").to_numpy()
        if group_labels.size != len(documents):
            raise MethodError(f"分组列 {group_column} 与文本列长度不一致。")
        group_rows = []
        for label in sorted(set(str(item) for item in group_labels)):
            block = scores[group_labels == label]
            if block.size == 0:
                continue
            group_rows.append(
                {
                    "group": label,
                    "documents": int(block.size),
                    "mean_score": round(float(block.mean()), 6),
                    "positive_ratio": round(float((block > 0).mean()), 4),
                    "negative_ratio": round(float((block < 0).mean()), 4),
                }
            )
        if not group_rows:
            raise MethodError(f"分组列 {group_column} 没有可用分组。")
        tables["groups"] = table_of(pd.DataFrame(group_rows), limit=50)
        notes.append(f"已按 {group_column} 分组对比情感，共 {len(group_rows)} 组。")
    if distribution_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.hist(
                scores, bins=max(5, min(20, len(scores) // 5)), color="#4f7cff", edgecolor="white"
            )
            axis.axvline(0.0, color="#4a5568", linewidth=1.0)
            axis.set_xlabel("情感得分")
            axis.set_ylabel("文档数")
            axis.set_title("情感得分分布")
            axis.grid(alpha=0.3)
            context.save(fig, "domain_sentiment_distribution")
        except ImportError:
            context.warn("未安装 matplotlib，跳过情感得分分布图。")
    if polarity_plot:
        try:
            import matplotlib.pyplot as plt

            palette = {"正面": "#38a169", "中性": "#9aa7bd", "负面": "#e24a4a"}
            fig, axis = plt.subplots(figsize=(6, 4.2))
            axis.bar(
                [str(label) for label in rows["label"]],
                rows["count"].to_numpy(),
                color=[palette.get(str(label), "#4f7cff") for label in rows["label"]],
            )
            axis.set_ylabel("文档数")
            axis.set_title("正负面文档占比")
            axis.grid(alpha=0.3, axis="y")
            context.save(fig, "domain_sentiment_polarity")
        except ImportError:
            context.warn("未安装 matplotlib，跳过正负面文档占比图。")
    return registry.result(
        "domain.sentiment",
        context.table,
        metrics={
            "text_column": name,
            "documents": len(documents),
            "positive": int((scores > 0).sum()),
            "negative": int((scores < 0).sum()),
            "neutral": int((scores == 0).sum()),
            "mean_score": round(float(scores.mean()), 6),
            "top_terms": top_terms,
            "negation_window": int(negation_window),
            "negation_flips": int(flipped_total),
            "detail_rows": int(detail_rows),
            "top_term": str(counts.index[0]),
            "positive_words": len(positive),
            "negative_words": len(negative),
        },
        tables=tables,
        notes=notes,
    )


def lda_topic(context):
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    name, documents = _text_column(context)
    topics = context.whole("topics", 3, 2, 30)
    words = context.whole("words", 8, 3, 30)
    minimum = context.whole("min_df", 1, 1, 50)
    ngram_max = context.whole("ngram_max", 1, 1, 3)
    learning = context.text("learning_method", "batch", ("batch", "online"))
    seed = context.whole("seed", 42, 0, 10**6)
    doc_prior = context.number("alpha", None, 0.001, 10.0)
    topic_prior = context.number("beta", None, 0.001, 10.0)
    topic_plot = context.flag("topic_plot", True)
    vectorizer = CountVectorizer(
        min_df=minimum, max_df=0.95, analyzer=_phrase_analyzer(_word_analyzer, ngram_max)
    )
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError as error:
        raise MethodError(
            f"无法切分文本：{error}。最少出现文档数 {minimum} 太高，请调低 min_df。"
        ) from error
    if matrix.shape[1] < topics:
        raise MethodError(f"词表只有 {matrix.shape[1]} 个词，无法形成 {topics} 个主题。")

    model = LatentDirichletAllocation(
        n_components=topics,
        random_state=seed,
        max_iter=20,
        learning_method=learning,
        doc_topic_prior=doc_prior,
        topic_word_prior=topic_prior,
    )
    distribution = model.fit_transform(matrix)
    terms = vectorizer.get_feature_names_out()

    rows = []
    topic_terms = []
    for index, component in enumerate(model.components_):
        order = np.argsort(-component)[:words]
        selected = [str(terms[position]) for position in order]
        topic_terms.append(
            (f"主题{index + 1}", selected, np.asarray(component, dtype=float)[order])
        )
        rows.append(
            {
                "topic": f"主题{index + 1}",
                "terms": "、".join(selected),
                "weight": round(float(distribution[:, index].mean()), 6),
            }
        )
    dominant = distribution.argmax(axis=1)
    counts = pd.Series(dominant).value_counts().sort_index()
    sizes = pd.DataFrame(
        {
            "topic": [f"主题{index + 1}" for index in counts.index],
            "documents": counts.to_numpy(),
            "ratio": numbers(counts.to_numpy() / max(len(documents), 1), 4),
        }
    )
    notes = [
        "LDA 假设每篇文档是若干主题的混合，每个主题是词上的分布。",
        f"词表只保留出现在至少 {minimum} 篇文档中的词。",
        "困惑度越低表示模型对语料拟合越好，但主题数并非越多越好，需要结合可解释性判断。",
    ]
    if doc_prior is not None or topic_prior is not None:
        notes.append("已手动指定 Dirichlet 先验，先验越小主题分布越稀疏、主题越集中。")
    if ngram_max > 1:
        notes.append(f"词表已加入最多 {ngram_max} 个词的词组，主题词可能以词组形式出现。")
    if learning != "batch":
        notes.append(f"变分推断方式为 {learning}，按小批量更新，结果与批量法略有差异。")
    if topic_plot:
        try:
            import matplotlib.pyplot as plt

            shown = topic_terms[:8]
            fig, axes = plt.subplots(
                len(shown), 1, figsize=(7, max(2.2 * len(shown), 4)), squeeze=False
            )
            for position, (title, names, weights) in enumerate(shown):
                axis = axes[position, 0]
                axis.barh(names[::-1], weights[::-1], color="#4f7cff")
                axis.set_title(title)
                axis.grid(alpha=0.3, axis="x")
            fig.tight_layout()
            context.save(fig, "domain_lda_topics")
        except ImportError:
            context.warn("未安装 matplotlib，跳过主题词分布图。")
    return registry.result(
        "domain.lda",
        context.table,
        metrics={
            "text_column": name,
            "documents": len(documents),
            "topics": topics,
            "vocabulary": int(matrix.shape[1]),
            "min_df": minimum,
            "alpha": None if doc_prior is None else round(float(doc_prior), 6),
            "beta": None if topic_prior is None else round(float(topic_prior), 6),
            "perplexity": round(float(model.perplexity(matrix)), 4),
        },
        tables={
            "topics": table_of(pd.DataFrame(rows), limit=topics),
            "document_topics": table_of(sizes, limit=topics),
        },
        notes=notes,
    )
