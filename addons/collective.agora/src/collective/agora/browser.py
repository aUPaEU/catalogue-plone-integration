import json
import logging
import re
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from lxml import html as html_parser
from Products.Five.browser import BrowserView
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.annotation import IAnnotations
from zope.interface import alsoProvides
from plone.app.textfield.value import RichTextValue

from .interfaces import IAgoraSyncSettings, IAgoraSyncedDocument, ensure_settings_registry
from .detail_fragment import (
    absolutize_css_urls,
    extract_detail_fragment,
    extract_inline_styles,
    extract_stylesheet_urls,
    merge_synced_fragment,
)

_logger = logging.getLogger(__name__)
_MODEL = re.compile(r'\bcatalogue-model\s*=\s*["\']([^"\']+)', re.IGNORECASE)


def _catalogue_models(site):
    """Return the unique catalogue models used by components on the site."""
    found = set()

    def walk(folder):
        for child in folder.objectValues():
            text = getattr(child, 'text', None)
            raw = getattr(text, 'raw', '') if text else ''
            found.update(_MODEL.findall(raw or ''))
            if hasattr(child, 'objectValues'):
                walk(child)

    walk(site)
    return sorted(found)


class _BulkSyncRequest:
    """Request facade used to reuse the single-model synchronizer."""

    method = 'POST'

    def __init__(self, request, model_name):
        self.response = request.response
        self._body = json.dumps({'model_name': model_name})

    def get(self, name, default=None):
        return self._body if name == 'BODY' else default


def _safe_segment(value):
    value = str(value) if value is not None else ''
    return value if value and value not in ('.', '..') and not any(
        c in value for c in '/\\?&#%'
    ) and not any(c.isspace() or ord(c) < 32 for c in value) else None


def _safe_site_path(value):
    value = str(value or '').strip()
    if not value:
        return ''
    if not value.startswith('/') or any(char in value for char in ('?', '#', '"', "'", '\\')):
        raise ValueError('Invalid Plone catalogue path')
    parts = [part for part in value.split('/') if part]
    if any(part in ('.', '..') for part in parts):
        raise ValueError('Invalid Plone catalogue path')
    return '/' + '/'.join(parts)


def _public_browser_base(api_base_url, configured):
    """Return the browser-facing Odoo origin without changing API requests."""
    configured = str(configured or '').strip().rstrip('/')
    if configured:
        return configured
    parts = urlsplit(api_base_url)
    if parts.hostname == 'host.docker.internal':
        # Useful default for the local compose setup. Production deployments
        # should set browser_base_url to their public Odoo origin.
        return urlunsplit((parts.scheme, 'localhost%s' % (':' + str(parts.port) if parts.port else ''), '', '', '')).rstrip('/')
    return '%s://%s' % (parts.scheme, parts.netloc)


def _rewrite_browser_urls(fragment, api_base_url, browser_base_url):
    """Replace Docker/local Odoo origins in browser-visible HTML attributes."""
    api_parts = urlsplit(api_base_url)
    browser_parts = urlsplit(browser_base_url)
    internal_hosts = {api_parts.hostname, 'host.docker.internal'}
    if browser_parts.hostname not in internal_hosts:
        internal_hosts.update({'localhost', '127.0.0.1'})
    internal_origins = set()
    for host in internal_hosts:
        if not host:
            continue
        for scheme in ('http', 'https'):
            internal_origins.add('%s://%s' % (scheme, host))
            if api_parts.port:
                internal_origins.add('%s://%s:%s' % (scheme, host, api_parts.port))
    browser_origin = '%s://%s' % (browser_parts.scheme, browser_parts.netloc)
    for element in fragment.iter():
        for attribute, value in list(element.attrib.items()):
            if not value:
                continue
            rewritten = value
            # This also catches nested URLs such as the `u=` parameter in
            # Facebook/LinkedIn share links.
            # Replace the most specific origins first. Otherwise replacing
            # ``http://localhost`` before ``http://localhost:8010`` leaves the
            # port behind and produces malformed values such as ``:8010:8010``.
            for origin in sorted(internal_origins, key=len, reverse=True):
                rewritten = rewritten.replace(origin, browser_origin)
            element.set(attribute, rewritten)
    return fragment


class AgoraSyncView(BrowserView):
    """Synchronize one Odoo catalogue into Plone without exposing its token."""

    def _settings(self):
        registry = getUtility(IRegistry)
        ensure_settings_registry(registry)
        return registry.forInterface(IAgoraSyncSettings)

    def _json(self, payload, status=200):
        self.request.response.setStatus(status)
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(payload, ensure_ascii=False)

    def _target_folder(self, path):
        current = self.context
        for segment in [part for part in path.strip('/').split('/') if part]:
            safe = _safe_segment(segment)
            if not safe:
                raise ValueError('Invalid Plone path')
            child = current.get(safe)
            if child is None:
                current.invokeFactory('Folder', id=safe, title=safe.replace('-', ' ').title())
                child = current.get(safe)
            current = child
        return current

    def _model_title(self, list_url, headers):
        """Read Odoo's human-readable model description with the API token."""
        try:
            response = requests.get(list_url + '/schema', headers=headers, timeout=30)
            response.raise_for_status()
            title = (response.json() or {}).get('model_display_name')
            if isinstance(title, str) and title.strip():
                return title.strip()
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            _logger.warning('Could not retrieve catalogue model description')
        return None

    def __call__(self):
        if self.request.method != 'POST':
            return self._json({'error': 'POST required'}, 405)
        try:
            payload = json.loads(self.request.get('BODY', '{}') or '{}')
        except (TypeError, ValueError):
            return self._json({'error': 'Invalid JSON body'}, 400)

        if not isinstance(payload, dict):
            return self._json({'error': 'JSON body must be an object'}, 400)

        model_name = str(payload.get('model_name') or '').strip()
        if not _safe_segment(model_name):
            return self._json({'error': 'model_name is required'}, 400)
        settings = self._settings()
        base_url = (settings.api_base_url or '').strip().rstrip('/')
        browser_base_url = _public_browser_base(base_url, getattr(settings, 'browser_base_url', ''))
        token = settings.api_token or ''
        if not base_url or not token:
            return self._json({'error': 'Catalogue API is not configured in Plone'}, 503)

        try:
            catalogue_path = _safe_site_path(payload.get('source_path'))
        except ValueError as exc:
            return self._json({'error': str(exc)}, 400)
        # The Plone location is independent of Odoo website page IDs.
        parent_path = 'resources/' + model_name
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
        list_url = urljoin(base_url + '/', quote(model_name, safe='.'))
        model_title = self._model_title(list_url, headers)
        try:
            # Update existing folders as well, even when the catalogue is empty.
            folder = self._target_folder(parent_path)
            if model_title and folder.title != model_title:
                folder.title = model_title
                folder.reindexObject()
            page = 1
            synced = 0
            while True:
                response = requests.get(list_url, headers=headers, params={'page': page, 'page_size': 500}, timeout=30)
                response.raise_for_status()
                items = (response.json() or {}).get('items') or []
                if not items:
                    break
                for item in items:
                    element_id = _safe_segment(item.get('id'))
                    fields = item.get('fields') or {}
                    detail_url = fields.get('detail_view_url') or fields.get('detail_url')
                    if not element_id:
                        continue
                    # Fetch the API's fragment response directly.  The
                    # catalogue list also exposes a browser-facing website
                    # URL for navigation, but that URL is a full Odoo page
                    # and is not the synchronization payload.
                    api_detail_url = '%s/%s' % (list_url, quote(element_id, safe=''))
                    detail_response = requests.get(
                        api_detail_url + '?response=html',
                        headers={'Authorization': 'Bearer ' + token, 'Accept': 'text/html'}, timeout=30,
                    )
                    detail_response.raise_for_status()
                    document_id = element_id
                    document = folder.get(document_id)
                    title = str((item.get('fields') or {}).get('name') or item.get('display_name') or document_id)
                    if document is None:
                        folder.invokeFactory('Document', id=document_id, title=title)
                        document = folder.get(document_id)
                    if not IAgoraSyncedDocument.providedBy(document):
                        alsoProvides(document, IAgoraSyncedDocument)
                    if hasattr(document, 'setLayout'):
                        document.setLayout('agora-detail')
                    document.title = title
                    detail_html = extract_detail_fragment(detail_response.text)
                    # Resolve images, links and embedded CSS URLs against Odoo, not Plone.
                    fragment = html_parser.fragment_fromstring(detail_html, create_parent='div')
                    fragment.make_links_absolute(detail_url or api_detail_url)
                    _rewrite_browser_urls(fragment, base_url, browser_base_url)
                    detail_html = ''.join(html_parser.tostring(child, encoding='unicode') for child in fragment)
                    previous_text = getattr(getattr(document, 'text', None), 'raw', '') or ''
                    document.text = RichTextValue(
                        merge_synced_fragment(previous_text, detail_html),
                        'text/html', 'text/html',
                    )
                    stylesheets = []
                    for stylesheet in extract_stylesheet_urls(detail_html):
                        stylesheet_url = urljoin(detail_url or api_detail_url, stylesheet)
                        try:
                            css_response = requests.get(
                                stylesheet_url,
                                # Asset URLs need no catalogue bearer token.
                                timeout=30,
                            )
                            css_response.raise_for_status()
                            stylesheets.append(absolutize_css_urls(
                                css_response.text, stylesheet_url,
                            ))
                        except requests.RequestException:
                            _logger.warning(
                                'Could not fetch Odoo stylesheet %s',
                                stylesheet_url, exc_info=True,
                            )
                    IAnnotations(document)['collective.agora.stylesheets'] = stylesheets
                    # Keep API-provided inline CSS outside RichTextValue. TinyMCE
                    # may sanitize style elements while editing, but rendering
                    # must remain identical after an editor save.
                    IAnnotations(document)['collective.agora.inline_styles'] = extract_inline_styles(
                        detail_response.text,
                    )
                    if catalogue_path:
                        IAnnotations(document)['collective.agora.catalogue_path'] = catalogue_path
                    document.reindexObject()
                    synced += 1
                if len(items) < 500:
                    break
                page += 1
            return self._json({'success': True, 'model_name': model_name, 'synced': synced})
        except requests.RequestException as exc:
            _logger.exception('Agora catalogue synchronization failed')
            return self._json({'error': 'Odoo catalogue request failed', 'detail': str(exc)}, 502)
        except (KeyError, TypeError, ValueError) as exc:
            return self._json({'error': str(exc)}, 400)


class AgoraSyncAllView(BrowserView):
    """Synchronize every catalogue model referenced by this Plone site."""

    def _json(self, payload, status=200):
        self.request.response.setStatus(status)
        self.request.response.setHeader('Content-Type', 'application/json; charset=utf-8')
        return json.dumps(payload, ensure_ascii=False)

    def __call__(self):
        if self.request.method != 'POST':
            return self._json({'error': 'POST required'}, 405)

        models = _catalogue_models(self.context)
        results = []
        total_synced = 0
        failed = False
        for model_name in models:
            result = AgoraSyncView(
                self.context, _BulkSyncRequest(self.request, model_name),
            )()
            try:
                payload = json.loads(result)
            except (TypeError, ValueError):
                payload = {'error': 'Invalid synchronization response'}
            payload['model_name'] = model_name
            if payload.get('success'):
                total_synced += payload.get('synced', 0)
            else:
                failed = True
            results.append(payload)

        return self._json({
            'success': not failed,
            'models': results,
            'catalogues': len(models),
            'synced': total_synced,
        }, 502 if failed else 200)
