"""Helpers for keeping only the reusable Odoo detail component."""

import re


_DETAIL_START = re.compile(
    r'<section\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bdetail-view-container\b)[^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_SECTION_TAG = re.compile(r'</?section\b[^>]*>', re.IGNORECASE | re.DOTALL)
_STYLESHEET = re.compile(
    r'<link\b(?=[^>]*\brel\s*=\s*["\'][^"\']*stylesheet[^"\']*["\'])[^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_INLINE_STYLE = re.compile(r'<style\b[^>]*>.*?</style\s*>', re.IGNORECASE | re.DOTALL)
_HREF = re.compile(r'\bhref\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_CSS_URL = re.compile(r'url\(\s*(["\']?)([^"\')]+)\1\s*\)', re.IGNORECASE)
_BREADCRUMB = re.compile(
    r'<ol\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bbreadcrumb\b)[^>]*>.*?</ol>',
    re.IGNORECASE | re.DOTALL,
)
_FIRST_HREF = re.compile(r'(\bhref\s*=\s*["\'])[^"\']*(["\'])', re.IGNORECASE)
_RETURN_LINK = re.compile(
    r'(<a\b[^>]*\bclass\s*=\s*["\'][^"\']*\bdetail-view-return-btn\b[^"\']*["\'][^>]*\bhref\s*=\s*["\'])[^"\']*(["\'])',
    re.IGNORECASE,
)


def extract_detail_fragment(value):
    """Return stylesheet links plus the Odoo detail component.

    The API normally already returns this shape, but extracting again in Plone
    makes synchronization safe when an older API response or an already stored
    full Odoo page is encountered.
    """
    if not value:
        return ''

    start_match = _DETAIL_START.search(value)
    if not start_match:
        return value

    depth = 1
    end = None
    for tag in _SECTION_TAG.finditer(value, start_match.end()):
        if tag.group(0).startswith('</'):
            depth -= 1
            if depth == 0:
                end = tag.end()
                break
        elif not tag.group(0).rstrip().endswith('/>'):
            depth += 1

    if end is None:
        return value

    stylesheets = _STYLESHEET.findall(value)
    styles = _INLINE_STYLE.findall(value)
    section = _INLINE_STYLE.sub('', value[start_match.start():end])
    return ''.join(stylesheets + styles) + section


def extract_detail_section(value):
    """Return only the detail section, without stylesheet tags."""
    fragment = extract_detail_fragment(value)
    if not fragment:
        return ''
    start_match = _DETAIL_START.search(fragment)
    return _INLINE_STYLE.sub('', fragment[start_match.start():] if start_match else fragment)


def extract_inline_styles(value):
    """Keep API-provided style tags, including media attributes."""
    return ''.join(_INLINE_STYLE.findall(value or ''))


def extract_stylesheet_urls(value):
    """Return stylesheet URLs found in an Odoo response."""
    urls = []
    for tag in _STYLESHEET.findall(value or ''):
        match = _HREF.search(tag)
        if match:
            urls.append(match.group(1))
    return urls


def rewrite_breadcrumb_link(value, target):
    """Point the detail breadcrumb back to its Plone catalogue page."""
    if not value or not target:
        return value or ''

    def replace_breadcrumb(match):
        breadcrumb = match.group(0)
        return _FIRST_HREF.sub(r'\1%s\2' % target, breadcrumb, count=1)

    value = _BREADCRUMB.sub(replace_breadcrumb, value, count=1)
    return _RETURN_LINK.sub(r'\1%s\2' % target, value, count=1)


def absolutize_css_urls(css, stylesheet_url):
    """Make relative URLs in downloaded Odoo CSS usable from Plone."""
    from urllib.parse import urljoin

    def replace(match):
        quote = match.group(1)
        target = match.group(2).strip()
        if target.startswith(('data:', 'http:', 'https:', '//', '#')):
            return match.group(0)
        return 'url(%s%s%s)' % (quote, urljoin(stylesheet_url, target), quote)

    return _CSS_URL.sub(replace, css or '')
