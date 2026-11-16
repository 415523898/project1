from flask import Blueprint, jsonify, request

from agent import ml_tools, retriever

rag_api = Blueprint("rag_api", __name__)


@rag_api.get("/search")
def search():
    query = request.args.get("q", "")
    raw_top_k = request.args.get("top_k", "4")
    try:
        top_k = int(raw_top_k)
    except ValueError:
        return jsonify({"error": "top_k 需为整数。"}), 400
    try:
        result = ml_tools.search({"query": query, "top_k": top_k})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


@rag_api.get("/status")
def status():
    return jsonify(retriever.RETRIEVER.status())
