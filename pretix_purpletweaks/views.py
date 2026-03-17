from django import forms
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextInput
from pretix.base.forms import SettingsForm
from django.http import HttpResponse
from pretix.base.models import Event
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.views.order import OrderDownload
from django.conf import settings

class PurpleSettingsForm(SettingsForm):
    block_multisubevent_checkout = forms.BooleanField(
        label=_("Block checkout with positions for multiple subevents"), required=False
    )
    onpremise_contact_availability = forms.ChoiceField(
        label=_("Let customers provide emergency contact information"),
        choices=[
            ("never", _("Never")),
            ("optional", _("Optional")),
            ("always", _("Always")),
        ],
    )
    event_page_css = forms.CharField(
        label=_("Event page CSS"),
        widget=forms.Textarea,
        required=False,
        help_text=_("CSS to render on event related pages. This feature must be enabled in the config file.")
    )


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = PurpleSettingsForm
    template_name = "pretix_purpletweaks/settings.html"
    permission = "can_change_event_settings"

    def get_success_url(self) -> str:
        return reverse(
            "control:event.settings",
            kwargs={
                "organizer": self.request.event.organizer.slug,
                "event": self.request.event.slug,
            },
        )


def custom_css(request, *args, **kwargs):
    event = request.event
    css_content = event.settings.event_page_css
    return HttpResponse(
        css_content,
        content_type="text/css",
    )
