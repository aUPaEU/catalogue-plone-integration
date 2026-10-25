from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper, RegistryEditForm

from .interfaces import IAgoraSyncSettings
from .interfaces import ensure_settings_registry
from plone.registry.interfaces import IRegistry
from zope.component import getUtility


class AgoraSyncControlPanel(RegistryEditForm):
    schema = IAgoraSyncSettings
    label = 'Àgora catalogue synchronization'

    def __init__(self, context, request):
        ensure_settings_registry(getUtility(IRegistry))
        super().__init__(context, request)

    def getContent(self):
        ensure_settings_registry(getUtility(IRegistry))
        return super().getContent()


class AgoraSyncControlPanelView(ControlPanelFormWrapper):
    form = AgoraSyncControlPanel

    def getContent(self):
        ensure_settings_registry(getUtility(IRegistry))
        return super().getContent()

    def __call__(self):
        ensure_settings_registry(getUtility(IRegistry))
        return super().__call__()
