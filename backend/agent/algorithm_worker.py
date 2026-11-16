"""Private file-based IPC with a trusted parent; never accepts requests over HTTP."""

import os
import pickle
import sys
from pathlib import Path


def main():
    if not sys.stdin.buffer.readline():
        return 1
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    request_path, result_path = map(Path, sys.argv[1:3])
    with request_path.open("rb") as stream:
        request = pickle.load(stream)
    try:
        from engine import registry

        prefix = request["args"][0].split(".")[0]
        layer = {
            "prep": "prepare",
            "describe": "stats",
            "test": "stats",
            "eval": "evaluate",
            "model": "modeling",
            "ml": "machine",
            "domain": "domain",
            "series": "series",
            "causal": "causal",
            "design": "causal",
        }.get(prefix)
        if layer:
            registry.load_implementations(layer)
        result = request["function"](*request["args"], **request["kwargs"])
        response = {"ok": True, "result": result, "notes": request["args"][1].notes}
    except Exception as error:
        response = {"ok": False, "error": str(error)[:600]}
    pending = result_path.with_suffix(".pending")
    with pending.open("wb") as stream:
        pickle.dump(response, stream, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(pending, result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
