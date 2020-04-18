from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_lazy


class PluginApp(AppConfig):
    name = 'pretix_purpletweaks'
    verbose_name = 'Purple Tweaks'

    class PretixPluginMeta:
        name = ugettext_lazy('Purple Tweaks')
        author = 'Felix Rindt'
        description = ugettext_lazy(
            'This plugin adds various small features.'
        )
        visible = True
        restricted = False
        version = '0.1.0'

    def ready(self):
        from . import signals  # NOQA

    @property
    def compatibility_errors(self):
        needed = []
        try:
            from pretix_cashpayment.payment import CashPayment
        except:
            needed.append("pretix-cashpayment")
        if needed:
            return [_("Error while looking for following payment providers: %s.") % ", ".join(needed)]
        return None

default_app_config = 'pretix_purpletweaks.PluginApp'
