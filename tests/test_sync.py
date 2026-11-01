"""Run with Plone's Python: python -m unittest discover -s tests."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collective.agora.browser import AgoraSyncView
from collective.agora.views import AgoraDetailView
from collective.agora.detail_fragment import (
    extract_detail_fragment, extract_inline_styles, extract_display_content,
    merge_synced_fragment, remove_back_to_top_controls,
)

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
        }) if key == 'BODY' else default
        self.view = AgoraSyncView(self.site, self.request)
        self.view._settings = lambda: SimpleNamespace(api_base_url=API, api_token='test-only')
        self.annotation_patch = patch('collective.agora.browser.IAnnotations', lambda doc: doc.annotations)
        self.annotation_patch.start()
        self.addCleanup(self.annotation_patch.stop)

    def schema_response(self, title='Research proposals'):
        result = Mock()
        result.json.return_value = {'model_display_name': title}
        return result

    def response(self, items=None):
        result = Mock(text=HTML)
        result.json.return_value = {'items': items}
        return result

    def test_import_css_paths_and_repeat_without_detail_url(self):
        item = {'id': 3, 'fields': {'name': 'Research proposal'}}
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(), self.response([item]), self.response(),
            self.schema_response(), self.response([item]), self.response(),
        ]) as get:
            self.assertEqual(json.loads(self.view())['synced'], 1)
            doc = self.site['resources'][MODEL]['3']
            self.assertEqual(json.loads(self.view())['synced'], 1)
        self.assertIs(doc, self.site['resources'][MODEL]['3'])
        self.assertEqual(list(self.site), ['resources'])
        self.assertEqual(doc.layout, 'agora-detail')
        self.assertIn('media="screen"', doc.text.raw)
        self.assertIn('media="screen"', doc.annotations['collective.agora.inline_styles'])
        self.assertIn('http://localhost:8010/web/image/3', doc.text.raw)
        self.assertIn('http://localhost:8010/web/image/1', doc.text.raw)
        self.assertNotIn('Odoo navigation', doc.text.raw)
        self.assertNotIn('Odoo footer', doc.text.raw)
        self.assertEqual(get.call_args_list[2].args[0], API + '/' + MODEL + '/3?response=html')
        self.assertEqual(get.call_count, 6, 'Embedded CSS must not require extra requests')
        with patch('collective.agora.views.IAnnotations', lambda doc: doc.annotations):
            detail = AgoraDetailView(doc, self.request)
            self.assertIn('media="screen"', detail.inline_styles)
            self.assertNotIn('<style', detail.html)
            self.assertIn('Nested content', detail.html)
            self.assertEqual(detail.stylesheets, [])
            doc.text = SimpleNamespace(raw='<!-- agora-sync-start --><section class="detail-view-container"><p>Proposal</p></section><!-- agora-sync-end -->')
            self.assertIn('media="screen"', detail.inline_styles)

    def test_old_odoo_path_does_not_determine_location(self):
        item = {'id': 3, 'fields': {'detail_view_url': 'https://odoo.example/offering/42/3'}}
        with patch('collective.agora.browser.requests.get', side_effect=[self.schema_response(), self.response([item]), self.response()]):
            self.assertTrue(json.loads(self.view())['success'])
        self.assertEqual(list(self.site['resources'][MODEL]), ['3'])
        self.assertNotIn('offering', self.site)

    def test_description_updates_existing_folder_without_changing_url(self):
        model = 'alliance_catalogue_app.course'
        self.request.get.side_effect = lambda *args: json.dumps({'model_name': model})
        folder = self.view._target_folder('resources/' + model)
        folder.reindexObject = Mock()
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response('Courses'), self.response([]),
        ]) as get:
            self.assertTrue(json.loads(self.view())['success'])
        self.assertIs(self.site['resources'][model], folder)
        self.assertEqual(folder.title, 'Courses')
        folder.reindexObject.assert_called_once()
        self.assertEqual(get.call_args_list[0].args[0], API + '/' + model + '/schema')
        self.assertEqual(get.call_args_list[0].kwargs['headers']['Authorization'], 'Bearer test-only')

    def test_missing_description_preserves_existing_title(self):
        folder = self.view._target_folder('resources/' + MODEL)
        folder.title = 'Custom catalogue title'
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(None), self.response([]),
        ]):
            self.assertTrue(json.loads(self.view())['success'])
        self.assertEqual(folder.title, 'Custom catalogue title')

    def test_pagination(self):
        first = [{'id': i, 'fields': {}} for i in range(1, 501)]
        def fetch(url, **kwargs):
            if url.endswith('/schema'):
                return self.schema_response()
            if url == API + '/' + MODEL:
                return self.response(first if kwargs['params']['page'] == 1 else [{'id': 501}])
            return self.response()
        with patch('collective.agora.browser.requests.get', side_effect=fetch) as get:
            self.assertEqual(json.loads(self.view())['synced'], 501)
        self.assertEqual(len(self.site['resources'][MODEL]), 501)
        self.assertEqual(get.call_count, 504)

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

    def test_author_content_survives_resynchronization(self):
        item = {'id': 3, 'fields': {'name': 'Research proposal'}}
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(), self.response([item]), self.response(),
        ]):
            self.assertEqual(json.loads(self.view())['synced'], 1)
        document = self.site['resources'][MODEL]['3']
        document.text = SimpleNamespace(
            raw='<p>Author heading</p>' + document.text.raw + '<p>Author footer</p>'
        )
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(), self.response([item]), self.response(),
        ]):
            self.assertEqual(json.loads(self.view())['synced'], 1)
        self.assertIn('Author heading', document.text.raw)
        self.assertIn('Author footer', document.text.raw)
        self.assertEqual(document.text.raw.count('Proposal'), 1)
        with patch('collective.agora.views.IAnnotations', lambda doc: doc.annotations):
            detail = AgoraDetailView(document, self.request)
            self.assertIn('Author heading', detail.html)
            self.assertIn('Author footer', detail.html)

    def test_existing_body_is_preserved_when_markers_are_added(self):
        item = {'id': 3, 'fields': {'name': 'Research proposal'}}
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(), self.response([item]), self.response(),
        ]):
            self.assertEqual(json.loads(self.view())['synced'], 1)
        document = self.site['resources'][MODEL]['3']
        existing = document.text.raw
        document.text = SimpleNamespace(raw=existing + '<p>Added later</p>')
        with patch('collective.agora.browser.requests.get', side_effect=[
            self.schema_response(), self.response([item]), self.response(),
        ]):
            self.assertEqual(json.loads(self.view())['synced'], 1)
        self.assertIn('Added later', document.text.raw)
        self.assertIn('agora-sync-start', document.text.raw)

    def test_odoo_back_to_top_control_is_removed(self):
        value = ('<div id="top" style="display:none">Empty Top</div>'
                 '<a href="/offering/19/1#top"><i class="fa fa-arrow-up"></i></a>'
                 '<ol class="breadcrumb"><li>Courses</li></ol>')
        cleaned = remove_back_to_top_controls(value)
        self.assertNotIn('fa-arrow-up', cleaned)
        self.assertNotIn('id="top"', cleaned)
        self.assertIn('breadcrumb', cleaned)


if __name__ == '__main__':
    unittest.main()
