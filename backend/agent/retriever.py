import hashlib
import json
import re
import threading

from agent import corpus
from config import (
    RETRIEVER_DEFAULT_TOP_K as DEFAULT_TOP_K,
)
from config import (
    RETRIEVER_MAX_TOP_K as MAX_TOP_K,
)

CHINESE = re.compile(r"[\u4e00-\u9fff]")
CHANNEL_WEIGHTS = {"name": 2.0, "bm25": 1.0, "vector": 0.35, "fallback": 0.25}

TASK_HINTS = {
    "classification": (
        "分类",
        "类别",
        "判别",
        "识别",
        "哪一类",
        "classification",
        "classify",
        "标签",
    ),
    "regression": ("回归", "预测数值", "房价", "连续值", "regression", "拟合值", "残差"),
    "clustering": ("聚类", "无监督", "分群", "模糊", "cluster", "隶属度"),
}

CAPABILITY_HINTS = {
    "preprocessing": ("标准化", "降维", "主成分", "pca", "尺度", "预处理"),
    "evaluation": ("评估", "指标", "混淆矩阵", "准确率", "rmse", "r2", "auc", "残差图"),
    "workflow": ("怎么选", "如何选", "流程", "步骤", "对比", "建议", "workflow"),
}


def _tokens(text):
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", lowered)
    for block in CHINESE.findall(lowered):
        tokens.append(block)
    for size in (2, 3):
        for index in range(len(lowered) - size + 1):
            chunk = lowered[index : index + size]
            if CHINESE.search(chunk):
                tokens.append(chunk)
    return tokens


def _document(entry):
    return corpus.entry_text(entry)


class Retriever:
    def __init__(self, persist_dir=None):
        self.entries = list(corpus.CORPUS)
        self.documents = [_document(entry) for entry in self.entries]
        self.fingerprint = hashlib.sha256(
            json.dumps(
                list(zip((entry["id"] for entry in self.entries), self.documents, strict=True)),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.lock = threading.Lock()
        self.collection = None
        self.vector_error = None
        self.persist_dir = persist_dir
        self.bm25 = None
        self.bm25_error = None
        self._search_lock = threading.Lock()
        self._vector_queries = {}
        self._vector_busy = False

    def _bounded_vector_rank(self, query, limit):
        key = (query, limit)
        with self._search_lock:
            if key in self._vector_queries:
                return self._vector_queries[key]
            if self.vector_error or self._vector_busy:
                return []
            self._vector_busy = True
        ready = threading.Event()

        def prepare():
            try:
                result = self._vector_rank(query, limit)
                with self._search_lock:
                    self._vector_queries[key] = result
                    if len(self._vector_queries) > 64:
                        self._vector_queries.pop(next(iter(self._vector_queries)))
            except Exception as error:
                self.vector_error = f"向量检索暂不可用：{type(error).__name__}: {error}"
            finally:
                with self._search_lock:
                    self._vector_busy = False
                ready.set()

        threading.Thread(target=prepare, name="rag-vector", daemon=True).start()
        # Never let a cold embedding model or its download block a tool call.
        ready.wait(0.04)
        with self._search_lock:
            return self._vector_queries.get(key, [])

    def _bm25_index(self):
        if self.bm25 is None and self.bm25_error is None:
            try:
                from rank_bm25 import BM25Okapi

                self.bm25 = BM25Okapi([_tokens(document) for document in self.documents])
            except ImportError as error:
                self.bm25_error = f"rank_bm25 未安装：{error}"
        return self.bm25

    def _vector_index(self):
        if self.collection is None and self.vector_error is None:
            with self.lock:
                if self.collection is None and self.vector_error is None:
                    try:
                        import chromadb

                        client = (
                            chromadb.PersistentClient(path=self.persist_dir)
                            if self.persist_dir
                            else chromadb.EphemeralClient()
                        )
                        # Content identity also changes when documents change without a count change.
                        collection = client.get_or_create_collection(
                            "ml_methods_" + self.fingerprint[:24]
                        )
                        if collection.count() != len(self.entries):
                            existing = collection.get()["ids"]
                            if existing:
                                collection.delete(ids=existing)
                            collection.add(
                                ids=[entry["id"] for entry in self.entries],
                                documents=self.documents,
                                metadatas=[
                                    {"capability": entry["capability"], "title": entry["title"]}
                                    for entry in self.entries
                                ],
                            )
                        self.collection = collection
                    except Exception as error:
                        self.vector_error = f"向量检索不可用：{type(error).__name__}: {error}"
        return self.collection

    def _vector_rank(self, query, limit):
        collection = self._vector_index()
        if collection is None:
            return []
        try:
            result = collection.query(query_texts=[query], n_results=min(limit, len(self.entries)))
        except Exception as error:
            self.vector_error = f"向量检索失败：{type(error).__name__}: {error}"
            return []
        ids = result.get("ids", [[]])[0]
        return [entry_id for entry_id in ids if corpus.by_id(entry_id)]

    def _bm25_rank(self, query, limit):
        index = self._bm25_index()
        if index is None:
            return []
        scores = index.get_scores(_tokens(query))
        order = sorted(range(len(scores)), key=lambda position: scores[position], reverse=True)
        return [self.entries[position]["id"] for position in order[:limit] if scores[position] > 0]

    def _name_rank(self, query, limit):
        normalized = re.sub(r"[\W_]+", "", query.lower())
        if not normalized:
            return []
        scored = []
        for entry in self.entries:
            names = (
                entry["id"],
                entry["id"].split(".")[-1],
                entry["title"].split("（")[0],
            )
            score = 0.0
            for raw in names:
                name = re.sub(r"[\W_]+", "", raw.lower())
                if len(name) < 3:
                    continue
                if name == normalized:
                    score += 100
                elif name in normalized:
                    score += len(name)
                elif normalized in name:
                    score += len(normalized) / len(name)
            if score:
                scored.append((score, entry["id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [method_id for _, method_id in scored[:limit]]

    def _fallback_rank(self, query, limit):
        tokens = set(_tokens(query))
        scored = [
            (len(tokens & set(_tokens(document))), entry["id"])
            for entry, document in zip(self.entries, self.documents, strict=True)
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [method_id for score, method_id in scored[:limit] if score > 0]

    def _hints(self, query):
        lowered = query.lower()
        tasks = [
            task for task, words in TASK_HINTS.items() if any(word in lowered for word in words)
        ]
        capabilities = [
            name
            for name, words in CAPABILITY_HINTS.items()
            if any(word in lowered for word in words)
        ]
        return tasks, capabilities

    def _rerank(self, query, candidates, top_k, ranks):
        tasks, capabilities = self._hints(query)
        tokens = set(_tokens(query))
        scored = []
        for position, entry in enumerate(candidates):
            score = 0.0
            for channel, rank in ranks.get(entry["id"], {}).items():
                score += 2.0 * CHANNEL_WEIGHTS.get(channel, 0.5) / (rank + 1)
            overlap = len(tokens & set(_tokens(_document(entry))))
            score += min(overlap, 12) * 0.002
            if capabilities and entry["capability"] in capabilities:
                score += 0.9
            if tasks and set(tasks) & set(entry["tasks"]):
                score += 0.5
            if "workflow" in capabilities and entry["capability"] == "workflow":
                score += 0.4
            scored.append((score, -position, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in scored[:top_k]]

    def retrieve(self, query, top_k=DEFAULT_TOP_K, use_vector=True):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("检索关键词不能为空。")
        top_k = max(1, min(int(top_k or DEFAULT_TOP_K), MAX_TOP_K))
        pool = max(top_k * 4, 10)
        vector_ids = self._bounded_vector_rank(query, pool) if use_vector else []
        bm25_ids = self._bm25_rank(query, pool)
        name_ids = self._name_rank(query, pool)
        ranks = {}
        for channel, ids in (("name", name_ids), ("vector", vector_ids), ("bm25", bm25_ids)):
            for rank, entry_id in enumerate(ids):
                ranks.setdefault(entry_id, {})[channel] = rank
        if not ranks:
            ranks = {
                method_id: {"fallback": index}
                for index, method_id in enumerate(self._fallback_rank(query, pool))
            }
        ordered = sorted(ranks, key=lambda entry_id: min(ranks[entry_id].values()))
        candidates = [corpus.by_id(entry_id) for entry_id in ordered[:pool]]
        ranked = self._rerank(query, [entry for entry in candidates if entry], top_k, ranks)
        return {
            "query": query,
            "top_k": top_k,
            "channels": {
                "name": len(name_ids),
                "vector": len(vector_ids),
                "bm25": len(bm25_ids),
                "vector_error": self.vector_error,
                "bm25_error": self.bm25_error,
            },
            "results": [
                {
                    **corpus.summary(entry),
                    "score": round(
                        sum(
                            CHANNEL_WEIGHTS.get(channel, 0.5) / (rank + 1)
                            for channel, rank in ranks.get(entry["id"], {}).items()
                        ),
                        6,
                    ),
                    "ranks": ranks.get(entry["id"], {}),
                }
                for entry in ranked
            ],
        }

    def retrieve_ids(self, query, top_k=DEFAULT_TOP_K, use_vector=True):
        return [item["id"] for item in self.retrieve(query, top_k, use_vector)["results"]]

    def context(self, query, top_k=DEFAULT_TOP_K, *, use_vector=True):
        outcome = self.retrieve(query, top_k, use_vector=use_vector)
        blocks = []
        for item in outcome["results"]:
            entry = corpus.by_id(item["id"])
            blocks.append(f"[{entry['id']}] {corpus.entry_text(entry)}")
        return outcome, "\n\n".join(blocks)

    def status(self):
        return {
            "entries": len(self.entries),
            "corpus_sha256": self.fingerprint,
            "vector": "ready"
            if self.collection is not None
            else ("unavailable" if self.vector_error else "lazy"),
            "vector_error": self.vector_error,
            "bm25": "ready"
            if self.bm25 is not None
            else ("unavailable" if self.bm25_error else "lazy"),
            "bm25_error": self.bm25_error,
        }


RETRIEVER = Retriever()
