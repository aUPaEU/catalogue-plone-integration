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
_SYNC_START = '<!-- agora-sync-start -->'
_SYNC_END = '<!-- agora-sync-end -->'


def _same_markup(left, right):
    return re.sub(r'\s+', ' ', left or '').strip() == re.sub(r'\s+', ' ', right or '').strip()
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
# Odoo includes this decorative link in the response.  Its Font Awesome icon
# is not available in Plone, so it becomes a stray square above the breadcrumb.
_BACK_TO_TOP = re.compile(
    r'<a\b[^>]*>\s*<i\b[^>]*\bfa-arrow-up\b[^>]*>.*?</i>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)
_HIDDEN_TOP = re.compile(
    r'<(?:div|span)\b[^>]*\bid\s*=\s*["\']top["\'][^>]*>.*?</(?:div|span)>',
    re.IGNORECASE | re.DOTALL,
)
_SHARE_LABEL = re.compile(
    r'<(?:span|div)\b[^>]*\bclass\s*=\s*["\'][^"\']*\bdetail-share-actions-label\b[^"\']*["\'][^>]*>.*?</(?:span|div)>',
    re.IGNORECASE | re.DOTALL,
)
_SHARE_CONTROL = re.compile(
    r'<(?:a|button)\b[^>]*\bclass\s*=\s*["\'][^"\']*\bdetail-view-share-button\b[^"\']*["\'][^>]*>.*?</(?:a|button)>',
    re.IGNORECASE | re.DOTALL,
)
_DUPLICATE_PORT = re.compile(
    r'(?P<scheme>https?)://(?P<host>[^/\s:]+):(?P<port>\d+):(?P=port)(?P<rest>[^\s"\'<>]*)',
    re.IGNORECASE,
)


def repair_browser_urls(value):
    """Repair malformed URLs saved by older synchronization versions."""
    if not value:
        return value or ''
    value = _DUPLICATE_PORT.sub(
        r'\g<scheme>://\g<host>:\g<port>\g<rest>', value,
    )
    return value.replace('http://host.docker.internal:8010', 'http://localhost:8010')


def remove_back_to_top_controls(value):
    """Remove Odoo's icon-only back-to-top controls from the detail fragment."""
    return _HIDDEN_TOP.sub('', _BACK_TO_TOP.sub('', value or ''))


def remove_share_controls(value):
    """Remove Odoo's social-sharing controls while keeping other actions."""
    value = value or ''
    return _SHARE_CONTROL.sub('', _SHARE_LABEL.sub('', value))


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
    section = remove_share_controls(remove_back_to_top_controls(
        _INLINE_STYLE.sub('', value[start_match.start():end])
    ))
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


def merge_synced_fragment(existing, imported):
    """Replace only the synchronized region, preserving author content."""
    existing = existing or ''
    imported = imported or ''
    start = existing.find(_SYNC_START)
    end = existing.find(_SYNC_END, start + len(_SYNC_START)) if start >= 0 else -1
    if start >= 0 and end >= 0:
        prefix = existing[:start]
        # The first marker migration kept the complete legacy imported body.
        # If it is exactly the same as that managed body, remove the duplicate.
        if _same_markup(prefix, existing[start + len(_SYNC_START):end]):
            prefix = ''
        return prefix + _SYNC_START + imported + _SYNC_END + existing[end + len(_SYNC_END):]
    # Legacy documents have no ownership boundary. Keep their complete body
    # intact and add a managed region for future updates.
    if existing.strip():
        return existing + _SYNC_START + imported + _SYNC_END
    return _SYNC_START + imported + _SYNC_END


def extract_display_content(value):
    """Return editable document content, without sync markers or CSS tags."""
    value = value or ''
    if _SYNC_START in value and _SYNC_END in value:
        start = value.find(_SYNC_START)
        end = value.find(_SYNC_END, start + len(_SYNC_START))
        prefix = value[:start]
        managed = value[start + len(_SYNC_START):end]
        suffix = value[end + len(_SYNC_END):]
        if _same_markup(prefix, managed):
            prefix = ''
        value = prefix + managed + suffix
        return remove_back_to_top_controls(_INLINE_STYLE.sub('', _STYLESHEET.sub('', value)))
    return extract_detail_section(value)


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
