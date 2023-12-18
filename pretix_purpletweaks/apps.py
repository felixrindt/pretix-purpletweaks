from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = "pretix_purpletweaks"
    verbose_name = "Pretix Purple Tweaks"

    class PretixPluginMeta:
        name = gettext_lazy("Pretix Purple Tweaks")
        author = "Felix Rindt"
        description = gettext_lazy(
            "This is a plugin for pretix that has various features that can be turned on/off."
        )
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2.7.0"

    def ready(self):
        from . import signals  # NOQA
