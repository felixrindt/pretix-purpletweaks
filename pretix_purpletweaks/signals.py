import json
from functools import partial

from django import forms
from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import ugettext_lazy as _
from i18nfield.strings import LazyI18nString
from pretix.base.services.cart import CartError
from pretix.base.signals import (
    layout_text_variables, register_data_exporters, register_data_shredders,
    register_notification_types, register_payment_providers,
    requiredaction_display, validate_cart,
)
from pretix.control.signals import (
    nav_event_settings, order_info as control_order_info,
)
from pretix.multidomain.urlreverse import eventreverse
from pretix.presale.signals import (
    checkout_confirm_page_content, checkout_flow_steps, contact_form_fields,
    front_page_bottom, html_head, order_info as presale_order_info,
    order_meta_from_request,
)
from pretix.presale.views.cart import cart_session

from .checkoutflow import ContactForm
from .payment import PurpleCashPayment, PurpleManualPayment
from .shredder import OnPremiseContactShredder


"""
PAYMENT PROVIDERS
"""

@receiver(register_payment_providers, dispatch_uid="payment_purpletweaks.registercash")
def register_cashpayment(sender, **kwargs):
    return PurpleCashPayment


@receiver(register_payment_providers, dispatch_uid="payment_purpletweaks.registerinvoice")
def register_manualpayment(sender, **kwargs):
    return PurpleManualPayment

"""
CONTACT STEP
"""

@receiver(checkout_flow_steps, dispatch_uid="payment_purpletweaks.checkoutflowstep1")
def register_contact_checkout_step(sender, **kwargs):
    from .checkoutflow import ContactStep
    return ContactStep

@receiver(contact_form_fields, dispatch_uid="pretix_purpletweaks.additionalcontactquestion")
def add_additional_contact_question(sender, **kwargs):
    if not sender.settings.get('onpremise_contact_availability', as_type=str) == 'optional':
        return {}
    return {'has_onpremise_contact': forms.BooleanField(
            label=_('Provide emergency contact'),
            required=False,
            help_text=_('Check if you want to provide seperate contact information for the duration of the event.'),
        )}

@receiver(order_meta_from_request, dispatch_uid="payment_purpletweaks.contactstep_ordermeta")
def register_order_meta_for_contact_step(sender, request, **kwargs):
    session = cart_session(request)
    if not (sender.settings.get('onpremise_contact_availability', as_type=str) == 'always' \
            or session.get('contact_form_data', {}).get('has_onpremise_contact', False)):
        return {}
    return {'onpremise_contact': session.get('onpremise_contact', {})}

@receiver(checkout_confirm_page_content, dispatch_uid="payment_purpletweaks.onpremise_contact_confirmpage_content")
def register_onpremise_contact_confirmpage_content(sender, request, **kwargs):
    session = cart_session(request)
    if not (sender.settings.get('onpremise_contact_availability', as_type=str) == 'always' \
            or session.get('contact_form_data', {}).get('has_onpremise_contact', False)):
        return ""
    from .checkoutflow import ContactForm
    session_info = session.get('onpremise_contact', {})
    contact_info = []
    if session_info:
        contact_info = ContactForm.label_formdata(session_info, sender).values()

    template = get_template('pretix_purpletweaks/onpremise_contact_card.html')
    return template.render({
        'message': '',
        'contact_info': contact_info,
        'panelclass': 'panel-contact panel-primary'
    })


@receiver(layout_text_variables, dispatch_uid="pretix_purpletweaks.layouttextvar_name")
def add_layout_text_variable(sender, **kwargs):
    def element(pos, order, event, identifier=None):
        if not order.meta_info or not 'onpremise_contact' in json.loads(order.meta_info):
            return ""
        return ContactForm.label_formdata(json.loads(order.meta_info)['onpremise_contact'], order.event)[identifier][1]

    def street_and_city(pos, order, event):
        if not order.meta_info or not 'onpremise_contact' in json.loads(order.meta_info):
            return ""
        data = ContactForm.label_formdata(json.loads(order.meta_info)['onpremise_contact'], order.event)
        # Make it single-line
        street = ", ".join(line.strip() for line in data['street'][1].splitlines())
        return street + ", " + data['city'][1]

    return {
            "purple_onpremise_name": {
                "label": _("Emergency Contact Name"),
                "editor_sample": "Maria Mayer",
                "evaluate": partial(element, identifier='name'),
            },
            "purple_onpremise_telephone": {
                "label": _("Emergency Contact Phone Number"),
                "editor_sample": "+01 0123 456789",
                "evaluate": partial(element, identifier='telephone'),
            },
            "purple_onpremise_street": {
                "label": _("Emergency Contact Street"),
                "editor_sample": "Waldweg 1",
                "evaluate": partial(element, identifier='street'),
            },
            "purple_onpremise_city": {
                "label": _("Emergency Contact City"),
                "editor_sample": "12345 Musterstadt",
                "evaluate": partial(element, identifier='city'),
            },
            "purple_onpremise_street_and_city": {
                "label": _("Emergency Contact Street and City"),
                "editor_sample": "Waldweg 1, 12345 Musterstadt",
                "evaluate": street_and_city,
            },
    }

@receiver(presale_order_info, dispatch_uid="pretix_purpletweaks.order_info_presale_onpremise_contact")
def register_order_info_presale_onpremise_contact(sender, order=None, **kwargs):
    return get_order_info_onpremise_contact(order, paneltype='panel-contact panel-primary')

@receiver(control_order_info, dispatch_uid="pretix_purpletweaks.order_info_control_onpremise_contact")
def register_order_info_control_onpremise_contact(sender, order=None, **kwargs):
    return get_order_info_onpremise_contact(order, paneltype='panel-default')


def get_order_info_onpremise_contact(order=None, paneltype='panel-default'):
    if not order:
        return ""
    contact_form_data = json.loads(order.meta_info).get('contact_form_data', {})
    template = get_template('pretix_purpletweaks/onpremise_contact_card.html')
    if not (order.event.settings.get('onpremise_contact_availability', as_type=str) == 'always' \
            or contact_form_data.get('has_onpremise_contact', False)):
        return ""
    else:
        return template.render({
            'message': '',
            'contact_info': ContactForm.label_formdata(json.loads(order.meta_info).get('onpremise_contact', ""), order.event).values(),
            'panelclass': paneltype
        })


"""
MISC
"""

@receiver(validate_cart, dispatch_uid="payment_purpletweaks.validate_cart_no_multiple_subevents")
def validate_cart(sender, positions=None, **kwargs):
    if not sender.has_subevents or not positions:
        return
    if not sender.settings.get('block_multisubevent_checkout', as_type=bool):
        return
    subevent = positions[0].subevent
    for pos in positions[1:]:
        if subevent != pos.subevent:
            raise CartError(_(
                "Sorry, you can only choose one event per order. "
                "Please create multiple orders to participate on multiple dates."
            ))


@receiver(nav_event_settings, dispatch_uid='pretix_purpletweaks.mainsettings')
def navbar_settings(sender, request, **kwargs):
    url = resolve(request.path_info)
    return [{
        'label': _('Purple Tweaks'),
        'url': reverse('plugins:pretix_purpletweaks:settings', kwargs={
            'event': request.event.slug,
            'organizer': request.organizer.slug,
        }),
        'active': url.namespace == 'plugins:pretix_purpletweaks' and url.url_name.startswith('settings'),
    }]

@receiver(register_data_shredders, dispatch_uid="register_onpremise_contact_shredder")
def register_shredder(sender, **kwargs):
    return [
        OnPremiseContactShredder,
    ]
