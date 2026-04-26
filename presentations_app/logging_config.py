"""Log format with worker node label: ``hostname`` or ``hostname/WORKER_NODE_ID``."""

from __future__ import annotations

import logging

from .worker_node import get_worker_node_label


class NodeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "worker_node"):
            record.worker_node = get_worker_node_label()  # type: ignore[attr-defined]
        return super().format(record)
