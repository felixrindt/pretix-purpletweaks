from django.urls import re_path

from . import views
from .views import SettingsView

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/settings/purple/$",
        SettingsView.as_view(),
        name="settings",
    ),
]

event_patterns = []
