"""Presentation app URL configuration."""

from django.urls import path

from .views import PresentationCreateView

urlpatterns = [
    path("", PresentationCreateView.as_view(), name="presentation-create"),
]
