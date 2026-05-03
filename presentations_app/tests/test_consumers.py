"""Tests for WebSocket consumers."""

from django.test import TransactionTestCase
from unittest.mock import AsyncMock
import uuid


class SendInitialStateErrorTest(TransactionTestCase):
    def test_initial_state_includes_error_for_failed_presentation(self):
        """_send_initial_state includes error field when last log is an error."""
        from presentations_app.consumers import PresentationProgressConsumer
        from presentations_app.models import Presentation, PresentationLog

        pid = uuid.uuid4()
        presentation = Presentation.objects.create(
            id=pid, topic="Test", language="en", slides_amount=10,
            grade=5, subject="Math", status="failed"
        )
        PresentationLog.objects.create(
            presentation=presentation,
            kind="error",
            message="Playwright timeout after 60s",
            stage="failed",
            percent=0,
            payload={},
        )

        consumer = PresentationProgressConsumer()
        consumer.presentation_id = str(pid)
        sent = []
        consumer.send_json = AsyncMock(side_effect=lambda data: sent.append(data))

        import asyncio
        asyncio.run(consumer._send_initial_state())

        self.assertEqual(len(sent), 1)
        msg = sent[0]
        self.assertEqual(msg["stage"], "failed")
        self.assertEqual(msg["error"], "Playwright timeout after 60s")

    def test_initial_state_excludes_error_for_queued_presentation(self):
        """_send_initial_state does not include error field for non-error logs."""
        from presentations_app.consumers import PresentationProgressConsumer
        from presentations_app.models import Presentation, PresentationLog

        pid = uuid.uuid4()
        presentation = Presentation.objects.create(
            id=pid, topic="Test", language="en", slides_amount=10,
            grade=5, subject="Math", status="processing"
        )
        PresentationLog.objects.create(
            presentation=presentation,
            kind="status",
            message="Queued for generation",
            stage="pending",
            percent=0,
            payload={},
        )

        consumer = PresentationProgressConsumer()
        consumer.presentation_id = str(pid)
        sent = []
        consumer.send_json = AsyncMock(side_effect=lambda data: sent.append(data))

        import asyncio
        asyncio.run(consumer._send_initial_state())

        self.assertEqual(len(sent), 1)
        msg = sent[0]
        self.assertNotIn("error", msg)
