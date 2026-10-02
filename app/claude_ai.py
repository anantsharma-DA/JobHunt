"""Claude (Anthropic), called through Anthropic's official Python SDK rather than the OpenAI-compatible format the
other services share. Used only when you add a Claude key on the Settings tab.

- The model list comes live from Anthropic's Models API, so new models appear without a JobHunt update.
- A JSON answer is requested with structured outputs, so Claude's reply always matches the schema.
- On the models that support it, Anthropic's server-side refusal fallback is switched on: if a safety filter
  declines a request, Anthropic reruns it on its recommended fallback model instead of failing.
"""
import anthropic

from app.ai import TIMEOUT, AIError

LABEL = "Claude"
# Current Claude models think before answering, and that thinking counts towards max_tokens; JobHunt's smaller limits
# (600 for a cover note) are raised to this so the answer itself is never cut off. Only tokens used are billed.
MIN_MAX_TOKENS = 16000
# Models that accept the server-side refusal fallback (beta "server-side-fallback-2026-07-01", fallbacks="default").
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client(key, timeout=None):
    # One retry only: when a model is busy, JobHunt's own fallback moves on to your next model sooner.
    return anthropic.Anthropic(api_key=key, timeout=timeout or TIMEOUT, max_retries=1)


def _reason(exc, model=None):
    """Anthropic's error, as a short message for the page (never the raw response)."""
    what = model or LABEL
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return f"{LABEL} did not accept your API key"
    if isinstance(exc, anthropic.NotFoundError):
        return f"{what} is not available on {LABEL}"
    if isinstance(exc, anthropic.RateLimitError):
        return f"{what} is rate-limited right now"
    if isinstance(exc, anthropic.APITimeoutError):
        return f"{what} did not answer in time"
    if isinstance(exc, anthropic.APIConnectionError):
        return f"Could not reach {LABEL}. Check your internet connection"
    if isinstance(exc, anthropic.BadRequestError):
        message = str(getattr(exc, "message", "") or "")
        if "credit balance" in message.lower():
            return f"{LABEL} says this key has no credit left"
        return f"{what} refused the request (HTTP 400)"
    if isinstance(exc, anthropic.APIStatusError):
        return f"{what} failed (HTTP {exc.status_code})"
    return f"{what} failed"


def list_models(key):
    """Every Claude model this key can use, by name: [{id, name, context, free}]."""
    if not key:
        raise AIError("Paste your Claude API key first, then fetch the models.")
    try:
        models = [m for m in _client(key, 60).models.list() if m.id.startswith("claude-")]
    except anthropic.APIError as exc:
        raise AIError(_reason(exc) + ".") from exc
    if not models:
        raise AIError(f"{LABEL} listed no usable models right now. Try again later.")
    out = [{"id": m.id, "name": m.display_name or m.id, "context": m.max_input_tokens, "free": False} for m in models]
    out.sort(key=lambda m: m["name"].lower())
    return out


def _split(messages):
    """OpenAI-style messages -> (system text, Claude messages). Claude takes the system prompt separately."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")]
    return system, rest


def call(key, model, messages, schema=None, max_tokens=4000, timeout=None):
    """One request to one Claude model. Returns the reply text (JSON text matching `schema` when one is given), or
    raises AIError with a reason, so the next model in your list is tried."""
    system, turns = _split(messages)
    params = {"model": model, "max_tokens": max(max_tokens, MIN_MAX_TOKENS), "messages": turns}
    if system:
        params["system"] = system
    if schema:
        params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    client = _client(key, timeout)
    try:
        if model in FALLBACK_MODELS:
            response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = client.messages.create(**params)
    except anthropic.APIError as exc:
        raise AIError(_reason(exc, model)) from exc
    if response.stop_reason == "refusal":
        raise AIError(f"{model} declined this request")
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AIError(f"{model} sent an empty answer")
    return text
