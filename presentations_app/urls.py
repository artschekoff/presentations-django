"""Presentation app URL configuration."""

from django.urls import path

from .views import (
    PresentationActiveView,
    PresentationCheckTaskIdsView,
    PresentationCreateView,
    PresentationRestartView,
)

urlpatterns = [
    path("", PresentationCreateView.as_view(), name="presentation-create"),
    path("active/", PresentationActiveView.as_view(), name="presentation-active"),
    path("check-task-ids/", PresentationCheckTaskIdsView.as_view(), name="presentation-check-task-ids"),
    path("<uuid:presentation_id>/restart/", PresentationRestartView.as_view(), name="presentation-restart"),
]
