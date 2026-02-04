"""presentations URL configuration."""

from django.contrib import admin
from django.urls import include, path

from presentations_app.views import (
    PresentationDownloadView,
    PresentationFileDownloadView,
    PresentationFormView,
)

urlpatterns = [
    path("", PresentationFormView.as_view(), name="presentation-form"),
    path("admin/", admin.site.urls),
    path("api/presentations/", include("presentations_app.urls")),
    path(
        "presentations/<uuid:presentation_id>/download/",
        PresentationDownloadView.as_view(),
        name="presentation-download",
    ),
    path(
        "presentations/<uuid:presentation_id>/files/<int:file_index>/download/",
        PresentationFileDownloadView.as_view(),
        name="presentation-file-download",
    ),
]
