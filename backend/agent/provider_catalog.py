"""Unified public presets; credential identifiers remain independent and stable."""

import json
from pathlib import Path

CATALOG = json.loads(
    (Path(__file__).resolve().parent / "assets/model-providers.json").read_text(encoding="utf-8")
)
FAMILIES = {item["id"]: item for item in CATALOG["model_families"]}
PRESETS = {item["id"]: item for item in CATALOG["providers"]}


def preset_id(identifier, explicit=None):
    if isinstance(explicit, str) and explicit in {*PRESETS, "custom"}:
        return explicit
    candidate = CATALOG["legacy_aliases"].get(identifier, identifier)
    return candidate if candidate in PRESETS else "custom"


def metadata(identifier, settings):
    return {**settings, "preset_id": preset_id(identifier, settings.get("preset_id"))}


def models_url(base, protocol):
    for preset in PRESETS.values():
        for endpoint in preset["endpoints"]:
            if (
                base.rstrip("/") == endpoint["base_url"].rstrip("/")
                and protocol in endpoint["protocols"]
            ):
                return endpoint.get("models_url")
    return None
