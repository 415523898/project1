from flask import Blueprint, jsonify, request

from agent.api.auth_api import require
from engine import sensevoice

speech_api = Blueprint("speech_api", __name__)


@speech_api.before_request
def guard():
    return require()


@speech_api.get("/status")
def status():
    return jsonify(sensevoice.status())


@speech_api.post("/transcribe")
def transcribe():
    upload = request.files.get("audio")
    if upload is not None:
        blob = upload.read()
    else:
        blob = request.get_data(cache=False)
    try:
        return jsonify(sensevoice.transcribe(blob))
    except sensevoice.SpeechError as error:
        return jsonify({"error": str(error), "code": error.code}), error.status
