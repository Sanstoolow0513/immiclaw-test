"""HTTP list-models and probe logic per api_family."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .config_loader import load_providers
from .models import ProviderEntry, ProvidersFile


def _snippet(text: str, limit: int = 500) -> str:
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "..."


def _json_error(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc), "error_type": type(exc).__name__}


def _http_err(status: int, body: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status_code": status,
        "body_snippet": _snippet(body),
    }


def provider_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def resolve_api_key(env_key: str) -> str | None:
    v = os.environ.get(env_key, "").strip()
    return v or None


def _openai_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _anthropic_headers(api_key: str, anthropic_version: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": anthropic_version,
        "Content-Type": "application/json",
    }


def _list_url_openai_anthropic(base: str, list_path: str) -> str:
    return f"{base.rstrip('/')}{list_path}"


def _list_url_gemini(base: str, list_path: str, api_key: str) -> str:
    q = urlencode({"key": api_key})
    return f"{base.rstrip('/')}{list_path}?{q}"


def parse_openai_style_model_ids(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    items = data.get("data")
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for it in items:
        if isinstance(it, dict) and it.get("id"):
            out.append(str(it["id"]))
    return out


def parse_volces_or_alt_model_ids(data: Any) -> list[str]:
    ids = parse_openai_style_model_ids(data)
    if ids:
        return ids
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        for it in data["models"]:
            if isinstance(it, dict):
                if it.get("id"):
                    ids.append(str(it["id"]))
                elif it.get("name"):
                    ids.append(str(it["name"]))
    return ids


def parse_anthropic_model_ids(data: Any) -> list[str]:
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        out: list[str] = []
        for it in data["data"]:
            if isinstance(it, dict) and it.get("id"):
                out.append(str(it["id"]))
        if out:
            return out
    return parse_openai_style_model_ids(data)


def parse_gemini_models(data: Any) -> list[tuple[str, bool]]:
    """Return (model_name, supports_generate_content)."""
    out: list[tuple[str, bool]] = []
    if not isinstance(data, dict):
        return out
    models = data.get("models")
    if not isinstance(models, list):
        return out
    for it in models:
        if not isinstance(it, dict):
            continue
        name = it.get("name")
        if not name:
            continue
        methods = it.get("supportedGenerationMethods") or []
        supports = isinstance(methods, list) and "generateContent" in methods
        out.append((str(name), supports))
    return out


def pick_gemini_model(models: list[tuple[str, bool]]) -> str | None:
    for name, ok in models:
        if ok:
            return name
    if models:
        return models[0][0]
    return None


def list_models(
    provider: ProviderEntry,
    base_url: str,
    api_key: str,
    client: httpx.Client,
    anthropic_version: str,
) -> dict[str, Any]:
    try:
        if provider.api_family == "gemini":
            if provider.auth_style == "query_key":
                url = _list_url_gemini(base_url, provider.list_path, api_key)
                headers = {"Content-Type": "application/json"}
            elif provider.auth_style == "x_goog_api_key":
                url = _list_url_openai_anthropic(base_url, provider.list_path)
                headers = {
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                }
            else:
                url = _list_url_openai_anthropic(base_url, provider.list_path)
                headers = _openai_headers(api_key)
            r = client.get(url, headers=headers)
        elif provider.api_family == "anthropic":
            url = _list_url_openai_anthropic(base_url, provider.list_path)
            r = client.get(url, headers=_anthropic_headers(api_key, anthropic_version))
        else:
            url = _list_url_openai_anthropic(base_url, provider.list_path)
            r = client.get(url, headers=_openai_headers(api_key))

        body = r.text
        if r.status_code >= 400:
            return {"ok": False, **_http_err(r.status_code, body)}

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"invalid JSON: {e}", "body_snippet": _snippet(body)}

        if provider.api_family == "gemini":
            parsed = parse_gemini_models(data)
            model_ids = [n for n, _ in parsed]
            preferred = pick_gemini_model(parsed)
            return {
                "ok": True,
                "status_code": r.status_code,
                "raw": data,
                "model_ids": model_ids,
                "preferred_model_id": preferred,
            }

        if provider.api_family == "anthropic":
            model_ids = parse_anthropic_model_ids(data)
        else:
            model_ids = parse_volces_or_alt_model_ids(data)

        return {
            "ok": True,
            "status_code": r.status_code,
            "raw": data,
            "model_ids": model_ids,
            "preferred_model_id": model_ids[0] if model_ids else None,
        }
    except httpx.HTTPError as e:
        return _json_error(e)


def probe_openai(
    base_url: str,
    chat_path: str,
    api_key: str,
    model: str,
    client: httpx.Client,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{chat_path}"
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        r = client.post(url, headers=_openai_headers(api_key), json=payload)
        body = r.text
        if r.status_code >= 400:
            return {"ok": False, "model": model, **_http_err(r.status_code, body)}
        return {"ok": True, "status_code": r.status_code, "model": model}
    except httpx.HTTPError as e:
        return {"ok": False, "model": model, **_json_error(e)}


def probe_anthropic(
    base_url: str,
    messages_path: str,
    api_key: str,
    model: str,
    client: httpx.Client,
    anthropic_version: str,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{messages_path}"
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    try:
        r = client.post(
            url,
            headers=_anthropic_headers(api_key, anthropic_version),
            json=payload,
        )
        body = r.text
        if r.status_code >= 400:
            return {"ok": False, "model": model, **_http_err(r.status_code, body)}
        return {"ok": True, "status_code": r.status_code, "model": model}
    except httpx.HTTPError as e:
        return {"ok": False, "model": model, **_json_error(e)}


def probe_gemini(
    base_url: str,
    model: str,
    api_key: str,
    client: httpx.Client,
    auth_style: str,
) -> dict[str, Any]:
    mid = model[7:] if model.startswith("models/") else model
    path = f"/v1beta/models/{quote(mid, safe='')}:generateContent"
    url = f"{base_url.rstrip('/')}{path}"
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": "ping"}]}],
        "generationConfig": {"maxOutputTokens": 1},
    }
    try:
        if auth_style == "query_key":
            full = f"{url}?{urlencode({'key': api_key})}"
            r = client.post(
                full,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
        elif auth_style == "x_goog_api_key":
            r = client.post(
                url,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        else:
            r = client.post(
                url,
                headers=_openai_headers(api_key),
                json=payload,
            )
        body = r.text
        if r.status_code >= 400:
            return {"ok": False, "model": model, **_http_err(r.status_code, body)}
        return {"ok": True, "status_code": r.status_code, "model": model}
    except httpx.HTTPError as e:
        return {"ok": False, "model": model, **_json_error(e)}


def probe_provider(
    provider: ProviderEntry,
    base_url: str,
    api_key: str,
    model: str | None,
    client: httpx.Client,
    cfg: ProvidersFile,
) -> dict[str, Any]:
    listed = list_models(provider, base_url, api_key, client, cfg.anthropic_version)
    if not listed.get("ok"):
        return {"list": listed, "probe": None, "skipped": False}

    use_model = model or provider.probe_model or listed.get("preferred_model_id")
    if not use_model:
        return {
            "list": listed,
            "probe": {"ok": False, "error": "no model id from list response"},
            "skipped": False,
        }

    if provider.api_family == "openai":
        chat = provider.chat_path or "/v1/chat/completions"
        pr = probe_openai(base_url, chat, api_key, use_model, client)
    elif provider.api_family == "anthropic":
        mp = provider.messages_path or "/v1/messages"
        pr = probe_anthropic(
            base_url,
            mp,
            api_key,
            use_model,
            client,
            cfg.anthropic_version,
        )
    else:
        pr = probe_gemini(
            base_url,
            use_model,
            api_key,
            client,
            provider.auth_style,
        )

    return {"list": listed, "probe": pr, "skipped": False}


def run_list_all(
    host: str,
    ports: list[int] | None,
    timeout: float,
    cfg: ProvidersFile | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    cfg = cfg or load_providers()
    selected = cfg.providers
    if ports is not None:
        port_set = set(ports)
        selected = [p for p in cfg.providers if p.port in port_set]

    results: list[dict[str, Any]] = []
    default_headers = {
        "User-Agent": "immiclaw-test/llm-proxy (httpx)",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=timeout, headers=default_headers) as client:
        for p in selected:
            key = resolve_api_key(p.env_key)
            base = provider_base_url(host, p.port)
            entry: dict[str, Any] = {
                "port": p.port,
                "name": p.name,
                "api_family": p.api_family,
                "base_url": base,
                "target_host": p.target_host,
            }
            if not key:
                entry["skipped"] = True
                entry["reason"] = f"missing env {p.env_key}"
                results.append(entry)
                continue
            entry["skipped"] = False
            lm = list_models(p, base, key, client, cfg.anthropic_version)
            if not include_raw and isinstance(lm.get("raw"), dict):
                lm = {k: v for k, v in lm.items() if k != "raw"}
            entry["list_models"] = lm
            results.append(entry)

    return {"proxy_host": host, "results": results}


def run_probe_all(
    host: str,
    ports: list[int] | None,
    timeout: float,
    model_override: str | None,
    cfg: ProvidersFile | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    cfg = cfg or load_providers()
    selected = cfg.providers
    if ports is not None:
        port_set = set(ports)
        selected = [p for p in cfg.providers if p.port in port_set]

    results: list[dict[str, Any]] = []
    default_headers = {
        "User-Agent": "immiclaw-test/llm-proxy (httpx)",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=timeout, headers=default_headers) as client:
        for p in selected:
            key = resolve_api_key(p.env_key)
            base = provider_base_url(host, p.port)
            entry: dict[str, Any] = {
                "port": p.port,
                "name": p.name,
                "api_family": p.api_family,
                "base_url": base,
                "target_host": p.target_host,
            }
            if not key:
                entry["skipped"] = True
                entry["reason"] = f"missing env {p.env_key}"
                results.append(entry)
                continue
            out = probe_provider(p, base, key, model_override, client, cfg)
            if not include_raw:
                lst = out.get("list")
                if isinstance(lst, dict) and "raw" in lst:
                    out = {
                        **out,
                        "list": {k: v for k, v in lst.items() if k != "raw"},
                    }
            entry["skipped"] = False
            entry.update(out)
            results.append(entry)

    return {"proxy_host": host, "results": results}
