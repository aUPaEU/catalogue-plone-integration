"""Run with Plone's Python: python -m unittest discover -s tests."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collective.agora.browser import AgoraSyncView
from collective.agora.views import AgoraDetailView
from collective.agora.detail_fragment import extract_detail_fragment, extract_inline_styles

MODEL = 'alliance_catalogue_app.researchproposals'
API = 'http://localhost:8010/catalogue-api/v2'
HTML = '''<html><head><style media="screen">.card {background:url(/web/image/1)}</style>
<style>@font-face {src:url(/web/font.woff)}</style></head><body><header>Odoo navigation</header>
<section class="detail-view-container"><section>Nested content</section>
<img src="/web/image/3"><p>Proposal</p></section><footer>Odoo footer</footer></body></html>'''


class Content(dict):
    def __init__(self, **attrs):
        super().__init__()
        self.__dict__.update(attrs)
        self.annotations = {}

    def invokeFactory(self, kind, id, title):
        self[id] = Content(title=title, portal_type=kind)

    def setLayout(self, name):
        self.layout = name

    def reindexObject(self):
        pass

    def portal_url(self):
        return 'https://plone.example/Plone1'


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.site = Content()
        self.request = Mock(method='POST')
        self.request.get.side_effect = lambda key, default=None: json.dumps({
            'model_name': MODEL, 'source_path': '/catalogue',
            'parent_path': 'old-place', 'preserve_odoo_path': True,
        }) if key == 'BODY' else default
        self.view = AgoraSyncView(self.site, self.request)
        self.view._settings = lambda: SimpleNamespace(api_base_url=API, api_token='test-only')
        self.annotation_patch = patch('collective.agora.browser.IAnnotations', lambda doc: doc.annotations)
        self.annotation_patch.start()
        self.addCleanup(self.annotation_patch.stop)

    def response(self, items=None):
        result = Mock(text=HTML)
        result.json.return_value = {'items': items}
        return result

    def test_import_css_paths_and_repeat_without_detail_url(self):
        item = {'id': 3, 'fields': {'name': 'Research proposal'}}
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.response([item]), self.response(), self.response([item]), self.response(),
        ]) as get:
            self.assertEqual(json.loads(self.view())['synced'], 1)
            doc = self.site['resources'][MODEL]['3']
            self.assertEqual(json.loads(self.view())['synced'], 1)
        self.assertIs(doc, self.site['resources'][MODEL]['3'])
        self.assertEqual(list(self.site), ['resources'])
        self.assertEqual(doc.layout, 'agora-detail')
        self.assertIn('media="screen"', doc.text.raw)
        self.assertIn('http://localhost:8010/web/image/3', doc.text.raw)
        self.assertIn('http://localhost:8010/web/image/1', doc.text.raw)
        self.assertNotIn('Odoo navigation', doc.text.raw)
        self.assertNotIn('Odoo footer', doc.text.raw)
        self.assertEqual(get.call_args_list[1].args[0], API + '/' + MODEL + '/3?response=html')
        self.assertEqual(get.call_count, 4, 'Embedded CSS must not require extra requests')
        detail = AgoraDetailView(doc, self.request)
        self.assertIn('media="screen"', detail.inline_styles)
        with patch('collective.agora.views.IAnnotations', lambda doc: doc.annotations):
            self.assertNotIn('<style', detail.html)
            self.assertIn('Nested content', detail.html)
            self.assertEqual(detail.stylesheets, [])

    def test_old_odoo_path_does_not_determine_location(self):
        item = {'id': 3, 'fields': {'detail_view_url': 'https://odoo.example/offering/42/3'}}
        with patch('collective.agora.browser.requests.get', side_effect=[self.response([item]), self.response()]):
            self.assertTrue(json.loads(self.view())['success'])
        self.assertEqual(list(self.site['resources'][MODEL]), ['3'])
        self.assertNotIn('offering', self.site)

    def test_pagination(self):
        first = [{'id': i, 'fields': {}} for i in range(1, 501)]
        def fetch(url, **kwargs):
            if url == API + '/' + MODEL:
                return self.response(first if kwargs['params']['page'] == 1 else [{'id': 501}])
            return self.response()
        with patch('collective.agora.browser.requests.get', side_effect=fetch) as get:
            self.assertEqual(json.loads(self.view())['synced'], 501)
        self.assertEqual(len(self.site['resources'][MODEL]), 501)
        self.assertEqual(get.call_count, 503)

    def test_invalid_model_and_missing_ids(self):
        self.request.get.side_effect = lambda *args: json.dumps({'model_name': '..'})
        with patch('collective.agora.browser.requests.get') as get:
            self.assertIn('error', json.loads(self.view()))
            get.assert_not_called()

    def test_styles_inside_and_outside_section_are_not_duplicated(self):
        value = '<style media="print">p{color:red}</style><section class="detail-view-container"><style>p{color:blue}</style><p>Hi</p></section>'
        fragment = extract_detail_fragment(value)
        self.assertEqual(fragment.count('<style'), 2)
        self.assertEqual(extract_inline_styles(fragment).count('<style'), 2)


if __name__ == '__main__':
    unittest.main()
