
from django.utils.translation import ugettext_lazy as _
from pretix.base.shredder import BaseDataShredder
from django.db import transaction
import json

class OnPremiseContactShredder(BaseDataShredder):
    verbose_name = _('Emergency Contact')
    identifier = 'onpremise_contact'
    description = _('This will remove customer on premise contact from orders.')

    def _contact(self, order):
        if not order.meta_info or not "onpremise_contact" in json.loads(order.meta_info):
            return {}
        return json.loads(order.meta_info)["onpremise_contact"]


    def generate_files(self):
        yield 'emergency_contact.json', 'application/json', json.dumps({
            order.code: self._contact(order)
            for order in self.event.orders.all() if self._contact(order)
        }, indent=4)

    @transaction.atomic
    def shred_data(self):
        for order in self.event.orders.all():
            meta_info = json.loads(order.meta_info or {})
            contact = meta_info.get("onpremise_contact", {})
            for key in contact.keys():
                contact[key] = '█'
            meta_info["onpremise_contact"] = contact
            if contact:
                order.meta_info = json.dumps(meta_info)
                order.save(update_fields=['meta_info'])


