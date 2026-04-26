from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from presentations_app.worker_node import get_worker_node_label


class WorkerNodeLabelTests(SimpleTestCase):
    @override_settings(WORKER_NODE_ID="worker-42")
    def test_label_contains_custom_id(self) -> None:
        self.assertIn("worker-42", get_worker_node_label())
        self.assertIn("/", get_worker_node_label())
