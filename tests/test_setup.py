import json
import unittest
from unittest.mock import patch

from collective.agora.setuphandlers import install
from plone.base.interfaces.controlpanel import IFilterSchema, ITinyMCESchema
from plone.base.interfaces.resources import IBundleRegistry
from plone.registry import Registry
from plone.registry.fieldfactory import persistentFieldAdapter, choicePersistentFieldAdapter
from zope.component import provideAdapter


class InstallationTest(unittest.TestCase):
    def test_merge_and_reinstall(self):
        provideAdapter(persistentFieldAdapter)
        provideAdapter(choicePersistentFieldAdapter)
        registry = Registry()
        registry.registerInterface(IFilterSchema, prefix='plone')
        registry.registerInterface(ITinyMCESchema, prefix='plone')
        registry.registerInterface(IBundleRegistry, prefix='plone.bundles/agora')
        legacy = registry.forInterface(IBundleRegistry, prefix='plone.bundles/agora')
        legacy.enabled = True
        legacy.jscompilation = 'https://cdn.jsdelivr.net/gh/KinoGlazPrusia/agora-component@v1.0.0/dist/agora-bundle.js'
        tiny = registry.forInterface(ITinyMCESchema, prefix='plone')
        tiny.other_settings = json.dumps({'custom_elements': 'existing-card', 'branding': False})
        tiny.templates = json.dumps([{'title': 'Existing', 'content': '<p>Keep</p>'}])
        tiny.custom_plugins = ['existing|++resource++existing.js']
        tiny.custom_buttons = ['existing']
        with patch('collective.agora.setuphandlers.getUtility', return_value=registry):
            install(None)
            first = {key: record.value for key, record in registry.records.items()}
            install(None)
        self.assertEqual(first, {key: record.value for key, record in registry.records.items()})
        self.assertFalse(legacy.enabled)
        loader = registry.records['plone.bundles/collective-agora.jscompilation'].value
        self.assertEqual(loader, '++resource++collective.agora/loader.js')
        self.assertIn('existing|++resource++existing.js', tiny.custom_plugins)
        self.assertEqual(json.loads(tiny.templates)[0]['title'], 'Existing')
        options = json.loads(tiny.other_settings)
        self.assertFalse(options['branding'])
        self.assertEqual(options['custom_elements'], 'existing-card,agora-component')
        filters = registry.forInterface(IFilterSchema, prefix='plone')
        self.assertTrue({'sync', 'catalogue-model', 'sync-parent', 'display-domain', 'media', 'type'} <= set(filters.custom_attributes))
        self.assertIn('style', filters.valid_tags)
        self.assertNotIn('style', filters.nasty_tags)
        self.assertIn('display-domain', options['extended_valid_elements'])
        self.assertIn('style[type|media]', options['extended_valid_elements'])
        filters = registry.forInterface(IFilterSchema, prefix='plone')
        self.assertFalse(filters.disable_filtering)
        self.assertIn('script', filters.nasty_tags)


if __name__ == '__main__':
    unittest.main()
