import json
import uuid
from django.test import TestCase, RequestFactory
from presentations_app.models import Presentation, PresentationLog
from presentations_app.views import PresentationActiveView


class PresentationActiveViewErrorTest(TestCase):
    def test_failed_presentation_includes_error_message(self):
        pid = uuid.uuid4()
        p = Presentation.objects.create(
            id=pid, topic="T", language="en", slides_amount=5,
            grade=3, subject="Sci", status="failed"
        )
        PresentationLog.objects.create(
            presentation=p, kind="error", message="Auth failed",
            stage="failed", percent=0, payload={}
        )

        factory = RequestFactory()
        request = factory.get("/api/presentations/active/")
        response = PresentationActiveView.as_view()(request)
        items = json.loads(response.content)
        failed = next(i for i in items if i["id"] == str(pid))
        self.assertEqual(failed["error_message"], "Auth failed")

    def test_non_failed_presentation_has_null_error_message(self):
        pid = uuid.uuid4()
        Presentation.objects.create(
            id=pid, topic="T", language="en", slides_amount=5,
            grade=3, subject="Sci", status="processing"
        )

        factory = RequestFactory()
        request = factory.get("/api/presentations/active/")
        response = PresentationActiveView.as_view()(request)
        items = json.loads(response.content)
        found = next((i for i in items if i["id"] == str(pid)), None)
        self.assertIsNotNone(found)
        self.assertIsNone(found["error_message"])
