"""Manual experiment and explanation orchestration; no HTTP/request globals."""

from agent import eventlog, experiment_store, experiments, result_explanation, session_access
from engine import account_datasets, datasets


def _explanation_context(root, owner, session, payload):
    if payload.get("experiment_id"):
        version = experiment_store.get(
            root, owner, session, payload["experiment_id"], payload.get("experiment_version")
        )
        actual = datasets.with_metadata(version["result"])
        method = payload.get("method")
        entry = actual if method == "__result" else actual.get("methods", {}).get(method)
        if not isinstance(entry, dict):
            raise ValueError("解读方法不属于该实验版本。")
        payload = {**payload, "data": entry.get("data") or actual.get("data")}
    return result_explanation.context(payload)


def explain(root, owner, session, settings, payload):
    value = _explanation_context(root, owner, session, payload)
    result = result_explanation.explain(
        owner, session, settings, value, payload.get("force") is True, root=root
    )
    # A deleted conversation must not receive a late explanation or response.
    session_access.check_session(root, owner, session)
    experiment_store.explanation(
        root,
        owner,
        session,
        payload.get("experiment_id"),
        payload.get("experiment_version"),
        payload.get("method"),
        result,
    )
    return result


def saved_explanation(root, owner, session, payload):
    value = _explanation_context(root, owner, session, payload)
    saved = result_explanation.saved(root, owner, session, value)
    if saved is None:
        saved = result_explanation.saved(root, owner, session, result_explanation.context(payload))
    saved = saved or {"text": ""}
    if saved.get("text"):
        experiment_store.explanation(
            root,
            owner,
            session,
            payload.get("experiment_id"),
            payload.get("experiment_version"),
            payload.get("method"),
            saved,
        )
    return saved


def prepare_run(root, owner, payload, context):
    """Resolve server-owned selection before entering the execution error boundary."""
    session = payload.get("session")
    if not session:
        session = eventlog.Store(root, owner).save(None, {"title": "本地实验"})["id"]
    selected = account_datasets.selection(root, owner, session)
    if selected and payload.get("source") == selected["dataset"]:
        context["selected_dataset"] = selected
    return session, context


def run(root, owner, project, payload, session, context):
    from agent import data_store

    runner = experiments.run_catalog if payload.get("methods") else experiments.run
    identifier = payload.get("experiment_id")
    base_version = payload.get("experiment_version")
    if identifier:
        experiment_store.get(root, owner, session, identifier, base_version)
    result = runner(
        payload,
        context or {},
        data_store.STORE,
        project,
        session_id=session,
        data_access=(root, owner),
    )
    if identifier:
        result = experiment_store.rerun(
            root,
            owner,
            session,
            identifier,
            base_version,
            result,
            payload.get("methods") or [payload.get("method")],
        )
    else:
        import uuid

        result = experiment_store.register(
            root, owner, session, result, "manual:" + uuid.uuid4().hex
        )
    return result
