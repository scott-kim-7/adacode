#!/usr/bin/env python3
"""Patch Open WebUI webui.db so Connections match the Ada Agent API.

Open WebUI persists admin connection settings in SQLite. Stale rows (e.g.
api_base_urls pointing at 127.0.0.1:8080 inside the container) override
docker-compose env vars and break GET /v1/models.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _ensure_openai(cfg: dict, agent_url: str, api_key: str) -> dict:
    openai = cfg.setdefault("openai", {})
    openai["enable"] = True
    openai["api_base_urls"] = [agent_url]
    openai["api_keys"] = [api_key]

    api_configs = openai.setdefault("api_configs", {})
    entry = api_configs.setdefault("0", {})
    entry["enable"] = True
    entry.setdefault("tags", [])
    entry.setdefault("prefix_id", "")
    entry["connection_type"] = "local"
    entry["auth_type"] = "bearer"
    # mlx_vlm / Ada agent expose chat/completions, not /responses
    entry.pop("api_type", None)
    return cfg


def _ensure_defaults(cfg: dict, model_id: str | None, pinned: str | None) -> dict:
    ui = cfg.setdefault("ui", {})
    if model_id:
        ui["default_models"] = model_id
    if pinned:
        ui["default_pinned_models"] = pinned
    return cfg


def patch_config(
    db_path: Path,
    agent_url: str,
    api_key: str = "local",
    model_id: str | None = None,
    pinned_model_id: str | None = None,
) -> dict[str, object]:
    agent_url = agent_url.rstrip("/")
    if not agent_url.endswith("/v1"):
        agent_url = f"{agent_url}/v1"

    pinned = pinned_model_id or model_id

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute("SELECT id, data FROM config ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            cfg: dict = {"version": 0}
            config_id = None
            before_models = None
        else:
            config_id, raw = row
            cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)

        before_urls = (cfg.get("openai") or {}).get("api_base_urls")
        before_models = (cfg.get("ui") or {}).get("default_models")
        cfg = _ensure_openai(cfg, agent_url, api_key)
        cfg = _ensure_defaults(cfg, model_id, pinned)

        data = json.dumps(cfg)
        if config_id is None:
            cur.execute(
                "INSERT INTO config (data, version) VALUES (?, 0)",
                (data,),
            )
        else:
            cur.execute(
                "UPDATE config SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (data, config_id),
            )
        con.commit()
    finally:
        con.close()

    return {
        "agent_url": agent_url,
        "model_id": model_id,
        "before_urls": before_urls,
        "after_urls": [agent_url],
        "before_models": before_models,
        "after_models": model_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="/app/backend/data/webui.db",
        help="Path to webui.db (default: container path)",
    )
    parser.add_argument(
        "--agent-url",
        required=True,
        help="Ada Agent OpenAI base URL (e.g. http://host.docker.internal:9082/v1)",
    )
    parser.add_argument("--api-key", default="local")
    parser.add_argument("--model-id", default="", help="ui.default_models value")
    parser.add_argument(
        "--pinned-model-id",
        default="",
        help="ui.default_pinned_models (defaults to --model-id)",
    )
    args = parser.parse_args()

    model_id = args.model_id.strip() or None
    pinned = args.pinned_model_id.strip() or None

    try:
        result = patch_config(
            Path(args.db),
            args.agent_url,
            api_key=args.api_key,
            model_id=model_id,
            pinned_model_id=pinned,
        )
    except Exception as exc:
        print(f"sync_openwebui_config: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
