"""Presentation app URL configuration."""

from django.urls import path

from .views import PresentationActiveView, PresentationCreateView, PresentationRestartView

urlpatterns = [
    path("", PresentationCreateView.as_view(), name="presentation-create"),
    path("active/", PresentationActiveView.as_view(), name="presentation-active"),
    path("<uuid:presentation_id>/restart/", PresentationRestartView.as_view(), name="presentation-restart"),
]
