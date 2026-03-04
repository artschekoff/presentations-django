"""Presentation app URL configuration."""

from django.urls import path

from .views import (
    PresentationActiveView,
    PresentationBulkCreateView,
    PresentationCheckTaskIdsView,
    PresentationCreateView,
    PresentationRestartView,
)

urlpatterns = [
    path("", PresentationCreateView.as_view(), name="presentation-create"),
    path("import/", PresentationBulkCreateView.as_view(), name="presentation-bulk-create"),
    path("active/", PresentationActiveView.as_view(), name="presentation-active"),
    path("check-task-ids/", PresentationCheckTaskIdsView.as_view(), name="presentation-check-task-ids"),
    path("<uuid:presentation_id>/restart/", PresentationRestartView.as_view(), name="presentation-restart"),
]
