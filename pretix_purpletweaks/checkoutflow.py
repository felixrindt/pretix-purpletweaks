
from collections import OrderedDict

from django import forms
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from pretix.base.forms.questions import NamePartsFormField
from pretix.base.models import InvoiceAddress
from pretix.base.settings import PERSON_NAME_SCHEMES
from pretix.presale import checkoutflow
from pretix.presale.views import CartMixin


class ContactForm(forms.Form):
    required_css_class = 'required'
    telephone = forms.CharField(label=_('Telephone'))
    street = forms.CharField(label=_("Address"),
            widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Street and Number')}),
            )
    zipcode = forms.CharField(label=_("ZIP code"))
    city = forms.CharField(label=_("City"))

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event')
        self.event = event
        self.request = kwargs.pop('request')
        initial = kwargs.get('initial', {})
        super().__init__(*args, **kwargs)
        self.fields = OrderedDict(self.fields)
        self.fields['name_parts'] = NamePartsFormField(
                    max_length=255,
                    required=True,
                    scheme=event.settings.name_scheme,
                    titles=event.settings.name_scheme_titles,
                    label=_('Name'),
                    initial=initial.get('name_parts', None),
        )
        self.fields.move_to_end('name_parts', last=False)

    @classmethod
    def label_formdata(cls, formdata, event):
        scheme = PERSON_NAME_SCHEMES[event.settings.name_scheme]
        try:
            name = scheme['concatenation'](formdata['name_parts']).strip()
        except AttributeError:
            name = formdata['name_parts']
        return OrderedDict([
            ('name', (_('Name'), name)),
            ('telephone', (_('Telephone'), formdata['telephone'])),
            ('street', (_('Address'), formdata['street'])),
            ('city', (_('ZIP code and city'), formdata['zipcode'] + " " + formdata['city'])),
        ])


class ContactStep(CartMixin, checkoutflow.TemplateFlowStep):
    identifier = 'onpremisecontact'
    priority = 55
    label = _("Emergency Contact")
    icon = 'volume-control-phone'
    template_name = 'pretix_purpletweaks/checkoutcontactstep.html'

    def is_completed(self, request, warn=False):
        self.request = request
        return True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cart'] = self.get_cart()
        ctx['contact_form'] = self.form
        return ctx

    @cached_property
    def form(self):
        initial = {}
        try:
            initial.update({
                    'name_parts': self.invoice_address.name_parts,
                    'street': self.invoice_address.street,
                    'zipcode': self.invoice_address.zipcode,
                    'city': self.invoice_address.city
            })
        except InvoiceAddress.DoesNotExist:
            pass
        telephone = self.cart_session.get('contact_form_data', {}).get('phone', None)
        if telephone:
            initial['telephone'] = telephone
        initial.update(self.cart_session.get('onpremise_contact', {}))
        return ContactForm(data=self.request.POST if self.request.method == "POST" else None,
                           event=self.request.event,
                           request=self.request,
                           initial=initial)

    def is_applicable(self, request):
        self.request = request
        optionalAndSelected = request.event.settings.get('onpremise_contact_availability', as_type=str) == 'optional' \
                and self.cart_session.get('contact_form_data', {}).get('has_onpremise_contact', False)
        alwaysAsk = request.event.settings.get('onpremise_contact_availability', as_type=str) == 'always'
        return alwaysAsk or optionalAndSelected

    def post(self, request):
        self.request = request
        failed = not self.form.is_valid()
        if failed:
            messages.error(request, _("We had difficulties processing your input. Please review the errors below."))
            return self.render()
        self.cart_session['onpremise_contact'] = self.form.cleaned_data
        return redirect(self.get_next_url(request))
