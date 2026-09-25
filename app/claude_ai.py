"""Claude, through Anthropic's official Python SDK.

Kept apart from app/ai.py, which speaks the OpenAI-compatible format the other services share. The key is sent only
to Anthropic.
"""
import anthropic

from app.ai import TIMEOUT, AIError

LABEL = "Claude"
SUGGESTED = "claude-opus-5"  # listed first; the user ticks whichever models they want
# Anthropic's servers rerun a request that the model's safety filter declines on another Claude model, instead of
# returning a refusal. Only these model families accept it; others are called without it.
FALLBACK_FAMILIES = ("claude-opus-5", "claude-fable-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client(key):
    # One retry on busy/5xx; after that the next model in the user's order gets its turn.
    return anthropic.Anthropic(api_key=key, timeout=float(TIMEOUT), max_retries=1)


def list_models(key):
    if not key:
        raise AIError("Paste your Claude API key first, then fetch the models.")
    try:
        models = list(_client(key).models.list())
    except anthropic.AuthenticationError as exc:
        raise AIError("Claude did not accept that API key.") from exc
    except anthropic.APIConnectionError as exc:
        raise AIError("Could not reach Claude. Check your internet connection.") from exc
    except anthropic.APIStatusError as exc:
        raise AIError(f"Claude answered with an error (HTTP {exc.status_code}).") from exc
    out = [{"id": m.id, "name": m.display_name or m.id, "context": getattr(m, "max_input_tokens", None), "free": False}
           for m in models]
    out.sort(key=lambda m: (m["id"] != SUGGESTED, m["name"].lower()))
    if not out:
        raise AIError("Claude listed no models for this key.")
    return out


def _split(messages):
    """OpenAI-style messages -> (system text, Claude messages). Claude takes the system prompt separately."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    return system, rest


def call(key, model, messages, schema=None, max_tokens=4000):
    """One request to one Claude model. Returns the reply text, or raises AIError so the next model can try."""
    system, rest = _split(messages)
    request = {"model": model, "max_tokens": max(max_tokens, 16000), "messages": rest}
    if system:
        request["system"] = system
    if schema:
        # Structured outputs: the reply is guaranteed to be JSON matching the schema.
        request["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    use_fallback = model.startswith(FALLBACK_FAMILIES)
    client = _client(key)
    for attempt in range(2):
        try:
            if use_fallback:
                response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **request)
            else:
                response = client.messages.create(**request)
            break
        except anthropic.BadRequestError as exc:
            if use_fallback and attempt == 0 and "fallback" in str(exc).lower():
                use_fallback = False  # this model or account doesn't take the fallback option; ask without it
                continue
            raise AIError(f"{model} refused the request: {str(exc)[:160]}") from exc
        except anthropic.AuthenticationError as exc:
            raise AIError("Claude did not accept your API key") from exc
        except anthropic.PermissionDeniedError as exc:
            raise AIError("this Claude key isn't allowed to use that model") from exc
        except anthropic.NotFoundError as exc:
            raise AIError(f"{model} is not available on Claude") from exc
        except anthropic.RateLimitError as exc:
            raise AIError(f"{model} is rate-limited right now") from exc
        except anthropic.APITimeoutError as exc:
            raise AIError(f"{model} did not answer (timeout)") from exc
        except anthropic.APIConnectionError as exc:
            raise AIError(f"could not reach Claude ({exc.__class__.__name__})") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code == 402 or "credit" in str(exc).lower():
                raise AIError("Claude says this key has no credit left") from exc
            raise AIError(f"{model} failed (HTTP {exc.status_code})") from exc

    if response.stop_reason == "refusal":
        raise AIError(f"{model} declined this request")
    if response.stop_reason == "max_tokens":
        raise AIError(f"{model}'s answer was cut off")
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise AIError(f"{model} sent an empty answer")
    return text
