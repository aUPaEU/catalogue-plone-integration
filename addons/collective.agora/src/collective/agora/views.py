from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.annotation import IAnnotations

from .detail_fragment import (
    extract_display_content,
    extract_detail_section,
    extract_inline_styles,
    extract_stylesheet_urls,
    remove_share_controls,
    repair_browser_urls,
    rewrite_breadcrumb_link,
)


class AgoraDetailView(BrowserView):
    """Render the imported detail inside Plone's normal site layout."""

    index = ViewPageTemplateFile('templates/agora_detail.pt')

    @property
    def html(self):
        text = getattr(self.context, 'text', None)
        html = remove_share_controls(repair_browser_urls(
            extract_display_content(getattr(text, 'raw', text) or '')
        ))
        catalogue_path = IAnnotations(self.context).get(
            'collective.agora.catalogue_path',
        )
        if catalogue_path:
            target = self.context.portal_url().rstrip('/') + catalogue_path
            html = rewrite_breadcrumb_link(html, target)
        return html

    @property
    def inline_styles(self):
        text = getattr(self.context, 'text', None)
        stored = IAnnotations(self.context).get('collective.agora.inline_styles', '')
        return repair_browser_urls(stored or extract_inline_styles(getattr(text, 'raw', text) or ''))

    @property
    def stylesheets(self):
        text = getattr(self.context, 'text', None)
        urls = extract_stylesheet_urls(getattr(text, 'raw', text) or '')
        stored = IAnnotations(self.context).get('collective.agora.stylesheets', ())
        # New synchronized documents store CSS text, while older documents
        # may still contain only stylesheet URLs.
        if stored:
            return [{'css': repair_browser_urls(css), 'url': ''} for css in stored]
        return [{'css': '', 'url': repair_browser_urls(url)} for url in urls]

    def __call__(self):
        return self.index()
