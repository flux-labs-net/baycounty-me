"""
llm.py - one way for the ingestion scripts to ask a model for structured JSON, from Anthropic (Claude) or OpenAI (GPT).

The model name picks the provider: names starting with gpt-, o1/o3/o4 or chatgpt- go to OpenAI, everything else to
Anthropic. So switching a step to GPT is just setting its model variable (for example MINUTES_MODEL=gpt-6.1-sol).

  structured(model, system, user, schema, name, max_tokens)  -> (answer, input_tokens, output_tokens)   one call
  batch_request(model, custom_id, ...)                        -> one request for a batch (half price)
  batch_submit(model, requests)                               -> batch id
  batch_state(model, batch_id)                                -> ("running", note) | ("ended", None) | ("failed", note)
  batch_results(model, batch_id)                              -> [BatchResult, ...]
  price(model, tin, tout, discount)                           -> estimated dollars, or None for an unknown model

Environment:
  Anthropic: ANTHROPIC_API_KEY (+ ANTHROPIC_WORKSPACE_ID if the key isn't scoped to a workspace)
  OpenAI:    OPENAI_API_KEY (+ OPENAI_PROJECT_ID / OPENAI_ORG_ID if the key needs them),
             OPENAI_REASONING_EFFORT (default low; "default" leaves it to the model) for reasoning models.
Standard library only, like the scripts that use it.
"""
import collections
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid

UA = "BayCounty.me ingestion (+https://baycounty.me)"
ANTHROPIC = "https://api.anthropic.com/v1"
OPENAI = "https://api.openai.com/v1"

# Published prices per million tokens (input, output), standard tier. Batches are half of these on both providers.
# Cached input is counted at the full input price, so estimates and caps err high.
# Anthropic: Haiku is listed "from" its price, so its estimate is a floor.
# OpenAI: developers.openai.com/api/docs/pricing, checked 2026-10-27 (short-context prices).
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.0, 20.0),
    "gpt-6-astra": (10.0, 50.0), "gpt-6.1-sol": (2.0, 10.0), "gpt-6.1-terra": (1.0, 5.0), "gpt-6-sol": (2.0, 10.0),
    "gpt-6-luna": (0.10, 0.50), "gpt-5.6-sol": (4.0, 20.0), "gpt-5.6-terra": (2.0, 12.0), "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.5": (5.0, 30.0), "gpt-5.4": (2.5, 15.0), "gpt-5.4-mini": (0.75, 4.50), "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.2": (1.75, 14.0), "gpt-5.1": (1.25, 10.0), "gpt-5": (1.25, 10.0), "gpt-5-mini": (0.25, 2.0),
    "gpt-5-nano": (0.05, 0.40), "gpt-4.1": (2.0, 8.0), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.5, 10.0), "gpt-4o-mini": (0.15, 0.60),
}
RETRY_CODES = (429, 500, 502, 503, 504, 529)


class SetupError(RuntimeError):
    """A problem with the run's setup (missing or bad key, workspace, billing, unknown model), not with one document:
    the caller stops the run instead of marking every document failed."""


def provider(model):
    return "openai" if re.match(r"^(gpt-|chatgpt-|o\d)", (model or "").lower()) else "anthropic"


def key_name(model):
    return "OPENAI_API_KEY" if provider(model) == "openai" else "ANTHROPIC_API_KEY"


def has_key(model):
    return bool(os.environ.get(key_name(model)))


def price(model, tin, tout, discount=1.0):
    p = PRICES.get(model)
    return round((tin * p[0] + tout * p[1]) / 1e6 * discount, 4) if p else None


def known(model):
    return model in PRICES


def _reasoning(model):
    """OpenAI reasoning models (gpt-5 and later, o-series) take reasoning_effort; older chat models reject it."""
    return bool(re.match(r"^(gpt-([5-9]|\d\d)|o\d)", model or ""))


def _effort():
    e = (os.environ.get("OPENAI_REASONING_EFFORT") or "low").strip().lower()
    return None if e == "default" else e


# ---------------------------------------------------------------------------------------------------------------
# HTTP

def _headers(model, content_type="application/json"):
    name = key_name(model)
    key = os.environ.get(name)
    if not key:
        raise SetupError("%s is not set (needed for %s)" % (name, model))
    if provider(model) == "openai":
        h = {"Authorization": "Bearer " + key}
        if os.environ.get("OPENAI_PROJECT_ID"):
            h["OpenAI-Project"] = os.environ["OPENAI_PROJECT_ID"]
        if os.environ.get("OPENAI_ORG_ID"):
            h["OpenAI-Organization"] = os.environ["OPENAI_ORG_ID"]
    else:
        h = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if os.environ.get("ANTHROPIC_WORKSPACE_ID"):  # needed when the key isn't scoped to a workspace
            h["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
    if content_type:
        h["content-type"] = content_type
    h["User-Agent"] = UA
    return h


def _label(model):
    return "OpenAI API" if provider(model) == "openai" else "Claude API"


def _is_setup(code, msg):
    if code in (401, 403, 404):  # bad key / no access / unknown model: every document would fail the same way
        return True
    if code == 400 and re.search(r"api key|workspace|credit|billing|model", msg, re.I):
        return True
    return code == 429 and re.search(r"insufficient_quota|billing|credit", msg, re.I)


def http(model, method, url, body=None, raw=False, data=None, content_type="application/json", tries=4, timeout=300):
    if body is not None:
        data = json.dumps(body).encode()
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, method=method, data=data, headers=_headers(model, content_type if data else None))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = r.read()
                return out if raw else json.loads(out.decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode("utf-8", "replace")
            if _is_setup(e.code, msg):
                raise SetupError("%s %s: %s" % (_label(model), e.code, msg))
            last = RuntimeError("%s %s: %s" % (_label(model), e.code, msg))
            if e.code not in RETRY_CODES:
                raise last
        except Exception as e:
            last = e
        time.sleep(5 * (attempt + 1))
    raise last


# ---------------------------------------------------------------------------------------------------------------
# Request bodies

def anthropic_params(model, system, user, schema, max_tokens):
    p = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": user}],
         "output_config": {"format": {"type": "json_schema", "schema": schema}}}
    if system:
        p["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    return p


def openai_body(model, system, user, schema, name, max_tokens):
    msgs = ([{"role": "developer" if _reasoning(model) else "system", "content": system}] if system else []) + \
           [{"role": "user", "content": user}]
    b = {"model": model, "messages": msgs,
         "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}}
    if _reasoning(model):
        # reasoning tokens count against this limit, so leave room on top of the answer itself
        b["max_completion_tokens"] = max_tokens + 16000
        if _effort():
            b["reasoning_effort"] = _effort()
    else:
        b["max_completion_tokens"] = max_tokens
    return b


def request_body(model, system, user, schema, name, max_tokens):
    if provider(model) == "openai":
        return openai_body(model, system, user, schema, name, max_tokens)
    return anthropic_params(model, system, user, schema, max_tokens)


# ---------------------------------------------------------------------------------------------------------------
# Reading an answer (same shape from a direct call or a batch line)

def parse_anthropic(msg):
    """-> (answer, tin, tout). Raises RuntimeError on refusal / cut-off / bad JSON (tokens still on the error)."""
    u = msg.get("usage") or {}
    tin = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
    tout = u.get("output_tokens") or 0
    if msg.get("stop_reason") in ("refusal", "max_tokens"):
        raise ModelStopped("model stopped: %s" % msg.get("stop_reason"), tin, tout)
    text = "".join(b.get("text", "") for b in msg.get("content") or [] if b.get("type") == "text")
    return _json(text, tin, tout), tin, tout


def parse_openai(resp):
    u = resp.get("usage") or {}
    tin, tout = u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0
    choice = (resp.get("choices") or [{}])[0]
    m = choice.get("message") or {}
    if m.get("refusal"):
        raise ModelStopped("model stopped: refusal", tin, tout)
    if choice.get("finish_reason") in ("length", "content_filter"):
        raise ModelStopped("model stopped: %s" % ("max_tokens" if choice["finish_reason"] == "length" else "refusal"), tin, tout)
    return _json(m.get("content") or "", tin, tout), tin, tout


class ModelStopped(RuntimeError):
    def __init__(self, msg, tin=0, tout=0):
        super().__init__(msg)
        self.tin, self.tout = tin, tout


def _json(text, tin, tout):
    try:
        return json.loads(text)
    except ValueError as e:
        raise ModelStopped("bad JSON: %s" % e, tin, tout)


def structured(model, system, user, schema, name, max_tokens, tries=3):
    """One direct call. -> (answer dict, input tokens, output tokens)."""
    if provider(model) == "openai":
        j = http(model, "POST", OPENAI + "/chat/completions", request_body(model, system, user, schema, name, max_tokens), tries=tries)
        return parse_openai(j)
    j = http(model, "POST", ANTHROPIC + "/messages", request_body(model, system, user, schema, name, max_tokens), tries=tries)
    return parse_anthropic(j)


# ---------------------------------------------------------------------------------------------------------------
# Batches (half price, results within 24 hours)

BatchResult = collections.namedtuple("BatchResult", "custom_id answer tin tout error")


def batch_request(model, custom_id, system, user, schema, name, max_tokens):
    body = request_body(model, system, user, schema, name, max_tokens)
    if provider(model) == "openai":
        return {"custom_id": custom_id, "method": "POST", "url": "/v1/chat/completions", "body": body}
    return {"custom_id": custom_id, "params": body}


def _multipart(fields, filename, content):
    boundary = "----bc" + uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode()
    out += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
            "Content-Type: application/jsonl\r\n\r\n" % (boundary, filename)).encode() + content + b"\r\n"
    out += ("--%s--\r\n" % boundary).encode()
    return out, "multipart/form-data; boundary=" + boundary


def batch_submit(model, requests):
    if provider(model) == "openai":
        jsonl = "\n".join(json.dumps(r) for r in requests).encode()
        data, ctype = _multipart({"purpose": "batch"}, "requests.jsonl", jsonl)
        f = http(model, "POST", OPENAI + "/files", data=data, content_type=ctype)
        b = http(model, "POST", OPENAI + "/batches", {"input_file_id": f["id"], "endpoint": "/v1/chat/completions",
                                                     "completion_window": "24h"})
        return b["id"]
    return http(model, "POST", ANTHROPIC + "/messages/batches", {"requests": requests})["id"]


def batch_model(model, batch_id):
    """Batches stored before the model was recorded: tell the provider from the id."""
    if model:
        return model
    return "gpt-5" if str(batch_id).startswith("batch_") else "claude-sonnet-5-5"


def batch_state(model, batch_id):
    if provider(model) == "openai":
        b = http(model, "GET", OPENAI + "/batches/" + batch_id)
        st = b.get("status")
        c = b.get("request_counts") or {}
        if st in ("completed", "expired", "cancelled"):
            return "ended", None
        if st == "failed":
            errs = ((b.get("errors") or {}).get("data") or [{}])
            return "failed", "batch failed: %s" % "; ".join(str(e.get("message") or e) for e in errs)[:400]
        return "running", "%s, %s done of %s" % (st, (c.get("completed") or 0) + (c.get("failed") or 0), c.get("total") or "?")
    b = http(model, "GET", ANTHROPIC + "/messages/batches/" + batch_id)
    if b.get("processing_status") == "ended":
        return "ended", None
    c = b.get("request_counts") or {}
    return "running", "%s done of %s" % (c.get("succeeded", 0) + c.get("errored", 0),
                                        sum(v for v in c.values() if isinstance(v, int)))


def _lines(raw):
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def batch_results(model, batch_id):
    out = []
    if provider(model) == "openai":
        b = http(model, "GET", OPENAI + "/batches/" + batch_id)
        for fid in (b.get("output_file_id"), b.get("error_file_id")):
            if not fid:
                continue
            for res in _lines(http(model, "GET", OPENAI + "/files/%s/content" % fid, raw=True)):
                cid, r = res.get("custom_id"), res.get("response") or {}
                if res.get("error") or r.get("status_code") != 200:
                    out.append(BatchResult(cid, None, 0, 0, json.dumps(res.get("error") or r.get("body") or res)[:500]))
                    continue
                out.append(_result(cid, parse_openai, r.get("body") or {}))
        return out
    b = http(model, "GET", ANTHROPIC + "/messages/batches/" + batch_id)
    for res in _lines(http(model, "GET", b["results_url"], raw=True)):
        cid, result = res.get("custom_id"), res.get("result") or {}
        if result.get("type") != "succeeded":
            out.append(BatchResult(cid, None, 0, 0, json.dumps(result.get("error") or result)[:500]))
            continue
        out.append(_result(cid, parse_anthropic, result.get("message") or {}))
    return out


def _result(cid, parse, msg):
    try:
        answer, tin, tout = parse(msg)
        return BatchResult(cid, answer, tin, tout, None)
    except ModelStopped as e:
        return BatchResult(cid, None, e.tin, e.tout, str(e))
