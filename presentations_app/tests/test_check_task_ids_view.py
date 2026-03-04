from __future__ import annotations

import json
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.urls import reverse

from presentations_app.models import Presentation


class PresentationCheckTaskIdsViewTests(TestCase):
    url = reverse("presentation-check-task-ids")
    auth_header = {"HTTP_AUTHORIZATION": "Bearer test-api-token"}

    def _create_presentation(self, task_id: str | None) -> Presentation:
        return Presentation.objects.create(
            topic="Topic",
            language="ru",
            slides_amount=10,
            grade=5,
            subject="math",
            task_id=task_id,
            status="pending",
        )

    @patch("presentations_app.views.API_TOKEN", "test-api-token")
    def test_rejects_non_list_task_ids(self) -> None:
        response = self.client.post(
            self.url,
            data=json.dumps({"task_ids": "not-a-list"}),
            content_type="application/json",
            **self.auth_header,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "task_ids must be a list of strings"})

    @patch("presentations_app.views.API_TOKEN", "test-api-token")
    def test_returns_existing_ids_in_unique_input_order(self) -> None:
        self._create_presentation("task-1")
        self._create_presentation("task-2")

        response = self.client.post(
            self.url,
            data=json.dumps(
                {"task_ids": ["task-2", "missing", "task-1", "task-2", "missing"]}
            ),
            content_type="application/json",
            **self.auth_header,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"existing": ["task-2", "task-1"]})

    @patch("presentations_app.views.API_TOKEN", "test-api-token")
    def test_uses_temp_table_path_for_postgresql(self) -> None:
        with (
            patch.object(connection, "vendor", "postgresql"),
            patch(
                "presentations_app.views.PresentationCheckTaskIdsView._existing_via_temp_table",
                return_value={"task-1"},
            ) as temp_table,
            patch(
                "presentations_app.views.PresentationCheckTaskIdsView._existing_via_batches",
                return_value=set(),
            ) as batches,
        ):
            response = self.client.post(
                self.url,
                data=json.dumps({"task_ids": ["task-1", "task-2", "task-1"]}),
                content_type="application/json",
                **self.auth_header,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"existing": ["task-1"]})
        temp_table.assert_called_once_with(["task-1", "task-2"])
        batches.assert_not_called()

    @patch("presentations_app.views.API_TOKEN", "test-api-token")
    def test_uses_batch_path_for_non_postgresql(self) -> None:
        with (
            patch.object(connection, "vendor", "sqlite"),
            patch(
                "presentations_app.views.PresentationCheckTaskIdsView._existing_via_batches",
                return_value={"task-2"},
            ) as batches,
            patch(
                "presentations_app.views.PresentationCheckTaskIdsView._existing_via_temp_table",
                return_value=set(),
            ) as temp_table,
        ):
            response = self.client.post(
                self.url,
                data=json.dumps({"task_ids": ["task-2", "task-1", "task-2"]}),
                content_type="application/json",
                **self.auth_header,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"existing": ["task-2"]})
        batches.assert_called_once_with(["task-2", "task-1"])
        temp_table.assert_not_called()
