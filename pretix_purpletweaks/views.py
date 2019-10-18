
from django import forms
from django.urls import resolve, reverse
from django.utils.translation import ugettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextarea, I18nTextInput
from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.views.event import (
    EventSettingsFormView, EventSettingsViewMixin,
)
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.views.order import OrderDownload


class PurpleSettingsForm(SettingsForm):
    block_multisubevent_checkout = forms.BooleanField(label=_('Block checkout with positions for multiple subevents'), required=False)
    onpremise_contact_availability = forms.ChoiceField(
                label=_("Let customers provide emergency contact information"),
                choices = [('never', _("Never")),
                           ('optional', _("Optional")),
                           ('always', _("Always")),
                ],
    )
    show_downloadarea = forms.BooleanField(label=_('Show download area to customer'), help_text=_("In the download area, all tickets of that order can be downloaded without restriction."), required=False)
    show_downloadarea_control = forms.BooleanField(label=_('Show download area in administrive interface'), required=False)
    downloadarea_heading = I18nFormField(
                widget=I18nTextInput,
                required=False,
                label=_("Download area heading"),
    )
    downloadarea_text = I18nFormField(
                widget=I18nTextInput,
                required=False,
                label=_("Download area text"),
    )


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = PurpleSettingsForm
    template_name = 'pretix_purpletweaks/settings.html'
    permission = 'can_change_event_settings'

    def get_success_url(self) -> str:
        return reverse('plugins:pretix_purpletweaks:settings', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })

