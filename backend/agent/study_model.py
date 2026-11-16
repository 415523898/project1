"""Provider options shared by route tools and session-card extraction."""

import copy

from agent.provider_options import Target
from config import (
    MODEL_DEFAULT_OUTPUT_TOKENS,
    MODEL_STRUCTURED_OUTPUT_TOKENS,
    MODEL_STRUCTURED_TEMPERATURE,
)


def structured_target(target, model):
    settings = copy.deepcopy(getattr(target, "options", {}))
    if model.lower().split("/")[-1].startswith("mimo-") and settings.get("protocol", "chat") in (
        "chat",
        "anthropic",
    ):
        # The wire adapter consumes target options after payload options; keep
        # the structured-job policy local without changing the saved profile.
        settings.update(
            protocol=settings.get("protocol", "chat"),
            family="mimo",
            effort="off",
            manual_mapping={},
        )
        return Target(str(target), settings)
    return target


def options(model, output_limit=None):
    name = model.lower().split("/")[-1]
    mimo, deepseek = name.startswith("mimo-"), "deepseek" in name
    limit = output_limit or (
        MODEL_STRUCTURED_OUTPUT_TOKENS if mimo or deepseek else MODEL_DEFAULT_OUTPUT_TOKENS
    )
    if mimo:
        return {
            "max_completion_tokens": limit,
            "thinking": {"type": "disabled"},
            "temperature": MODEL_STRUCTURED_TEMPERATURE,
        }
    return {
        "max_tokens": limit,
        **(
            {"reasoning_effort": "low"}
            if deepseek
            else {"temperature": MODEL_STRUCTURED_TEMPERATURE}
        ),
    }


def streaming(model):
    # MiMo returns complete tool arguments and usage in its JSON response.
    return not model.lower().split("/")[-1].startswith("mimo-")
