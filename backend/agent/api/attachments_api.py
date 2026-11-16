from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from agent import eventlog
from agent.api.auth_api import current, require
from agent.api.session_access import check_session
from config import USER_ROOT
from engine import account_datasets
from engine import chat_attachments as attachments
from engine import uploads

attachments_api = Blueprint("attachments_api", __name__)


@attachments_api.before_request
def guard():
    return require()


@attachments_api.post("")
def upload():
    try:
        session = check_session(request.form.get("session"))
        file = request.files.get("file")
        if file is None:
            raise ValueError("请选择附件。")
        audio = request.files.get("wav")
        name = file.filename or "未命名文件"
        blob = file.read()
        record = attachments.save(
            USER_ROOT,
            current(),
            session,
            name,
            blob,
            identifier=request.form.get("id"),
            audio_error=request.form.get("audio_error"),
            wav=audio.read() if audio is not None else None,
        )
        if Path(name).suffix.lower() in uploads.SUFFIXES:
            # Tables uploaded in a conversation also become reusable account datasets.
            try:
                dataset = account_datasets.save(USER_ROOT, current(), name, blob)
            except ValueError:
                dataset = None
            if dataset:
                record.update(
                    dataset_id=dataset["id"],
                    dataset_label=dataset["label"],
                    note="表格内容；已加入数据集「%s」，可在左侧数据集页使用。" % dataset["label"],
                )
        return jsonify(record)
    except (ValueError, OSError) as error:
        return jsonify({"error": str(error)}), 400


@attachments_api.get("/<session>/<identifier>/<action>")
def retrieve(session, identifier, action):
    try:
        check_session(session)
        log = eventlog.SessionLog(USER_ROOT, current(), session)
        record = attachments.authorized(log, identifier, request.args.get("message"))
        folder = attachments.asset(USER_ROOT, current(), session, identifier)
        if action == "text":
            return jsonify(
                attachments.read(
                    log, {"attachment_id": identifier, "message_id": request.args.get("message")}
                )
            )
        if action == "preview" and record["read_status"] == "image":
            return send_file(folder / "preview.jpg", mimetype="image/jpeg", max_age=0)
        if action != "download":
            raise ValueError("附件操作无效。")
        return send_file(
            folder / "original",
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=record["name"],
            max_age=0,
        )
    except (ValueError, OSError) as error:
        return jsonify({"error": str(error)}), 404


@attachments_api.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
