from django.urls import re_path

from . import views
from .views import SettingsView, custom_css

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/settings/purple/$",
        SettingsView.as_view(),
        name="settings",
    ),
]

event_patterns = [
    re_path(
        r"custom.css",
        custom_css,
        name="custom_css",
    )
]
