import json
from collections import OrderedDict
from datetime import datetime, time
from itertools import chain

from django import forms
from django.template import Context, Template
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from i18nfield.fields import I18nFormField, I18nTextarea
from i18nfield.strings import LazyI18nString
from pretix.base.models import Order
from pretix.base.payment import ManualPayment, BasePaymentProvider
from pretix.base.templatetags.rich_text import rich_text
from pretix.presale.views.cart import get_or_create_cart_id
from pretix_cashpayment.payment import CashPayment

from .datediff import (
    DateDiffField, DateDiffWidget, DateDiffWrapper,
    date_diff_wrapper_from_string,
)


class PurplePaymentMixin(object):
    @property
    def identifier(self):
        return "purple_{}".format(super().identifier)

    @property
    def verbose_name(self):
        return "Purple {}".format(super().verbose_name)

    @property
    def settings_form_fields(self) -> dict:
        """ 
        Returns an ordered dict of form fields for the payment settings form in pretix/control.
        In addition to the fields provided by BasePaymentProvider, this returns fields where
        the user can select, wether this payment method should not be shown to individual
        or business customers.
        """
        supdict = super().settings_form_fields
        myitems = [
            ('_block_individual_customers',
             forms.BooleanField(
                 label=_('Block for individual customers'),
                 help_text=_('If enabled, customers who selected \'individual\' in the invoice form wont see this payment method.'),
                 required=False
             )),
            ('_block_business_customers',
             forms.BooleanField(
                 label=_('Block for business customers'),
                 help_text=_('If enabled, customers who selected \'business\' in the invoice form wont see this payment method.'),
                 required=False
             )),
            ('_overwrite_expires',
             DateDiffField(
                 label=_('Overwrite expiration date'),
                 help_text=_('If enabled, the configured payment term will be overwritten and the order\'s expiration date will be set accordingly.'),
                 required=False,
             )),]
        return OrderedDict(list(supdict.items()) + myitems)

    def _is_allowed_for_customer_type(self, request=None, order=None):
        """
        Checks wether the customer should see this payment method based on them being 
        an individual or business customer. If the invoice address is not required or asked
        this check always returns True and thus doesn't block anything.
        """
        if not self.event.settings.get('invoice_address_asked', as_type=bool):
            return True
        if request and not hasattr(request, '_checkout_flow_invoice_address'):
            return True
        block_indi = self.settings.get('_block_individual_customers', as_type=bool)
        block_busi = self.settings.get('_block_business_customers', as_type=bool)
        if order:
            is_business = order.invoice_address.is_business
        else:
            is_business = request._checkout_flow_invoice_address.is_business
        if is_business:
            return not block_busi
        else:
            return not block_indi

    def is_allowed(self, request, total=None) -> bool:
        """
        You can use this method to disable this payment provider for certain groups
        of users, products or other criteria. If this method returns ``False``, the
        user will not be able to select this payment method. This will only be called
        during checkout, not on retrying.
        """
        return self._is_still_available(cart_id=get_or_create_cart_id(request)) and self._is_allowed_for_customer_type(request=request)

    def order_change_allowed(self, order) -> bool:
        """
        Will be called to check whether it is allowed to change the payment method of
        an order to this one.
        This implementation checks for the _availability_date setting to be either unset or in the future
        aswell as wether the customer should see this payment method based on the invoice form
        """
        # return self._is_still_available(order=order) and self._i, total=_is_allowed_for_customer_type(order=order)
        return False

    def execute_payment(self, request, payment) -> str:
        super().execute_payment(request, payment)
        order = payment.order
        expiration_date = self.settings.get('_overwrite_expires', as_type=DateDiffWrapper)
        if expiration_date:
            expiration_date = date_diff_wrapper_from_string(expiration_date)
            order.expires = expiration_date.datetime(order).replace(hour=23, minute=59, second=59)
            order.save()


class PurpleCashPayment(PurplePaymentMixin, CashPayment):
    pass

class PurpleManualPayment(PurplePaymentMixin, ManualPayment):
    is_implicit = False
