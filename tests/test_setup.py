import json
import unittest
from unittest.mock import patch

from collective.agora.setuphandlers import install
from plone.base.interfaces.controlpanel import IFilterSchema, ITinyMCESchema
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
        self.assertIn('existing|++resource++existing.js', tiny.custom_plugins)
        self.assertEqual(json.loads(tiny.templates)[0]['title'], 'Existing')
        options = json.loads(tiny.other_settings)
        self.assertFalse(options['branding'])
        self.assertEqual(options['custom_elements'], 'existing-card,agora-component')
        filters = registry.forInterface(IFilterSchema, prefix='plone')
        self.assertTrue({'sync', 'catalogue-model', 'sync-parent', 'display-domain'} <= set(filters.custom_attributes))
        self.assertIn('display-domain', options['extended_valid_elements'])
        filters = registry.forInterface(IFilterSchema, prefix='plone')
        self.assertFalse(filters.disable_filtering)
        self.assertIn('script', filters.nasty_tags)


if __name__ == '__main__':
    unittest.main()
