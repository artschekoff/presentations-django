"""Label for the running process: hostname + optional WORKER_NODE_ID (from env/settings)."""

from __future__ import annotations

import os
import socket


def get_worker_node_label() -> str:
    host = socket.gethostname()
    try:
        from django.conf import settings

        node_id = (getattr(settings, "WORKER_NODE_ID", None) or "").strip()
    except Exception:  # pragma: no cover  # before Django is configured
        node_id = (os.environ.get("WORKER_NODE_ID") or "").strip()
    if node_id:
        return f"{host}/{node_id}"
    return host
