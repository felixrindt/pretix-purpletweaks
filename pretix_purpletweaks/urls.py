from django.conf.urls import url

from . import views
from .views import SettingsView

urlpatterns = [
    url(r'^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/settings/purple/$',
        SettingsView.as_view(), name='settings'),
]

event_patterns = []
