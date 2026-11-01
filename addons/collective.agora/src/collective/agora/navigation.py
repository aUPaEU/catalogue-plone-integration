"""Adapt Plone's navigation portlet for synchronized Agora documents.

Plone's navigation portlet does not expose extension points for the two
internal methods used here. The wrappers below are therefore deliberately
small and preserve the original methods, including when a development reload
imports this module more than once.
"""

from zope.component import adapter
from zope.interface import Interface, implementer
from zope.annotation import IAnnotations

from plone.app.portlets.portlets.navigation import (
    NavtreeStrategy,
    QueryBuilder,
    Renderer,
)
from plone.app.uuid.utils import uuidToObject
from plone.app.layout.navigation.interfaces import INavtreeStrategy

from .interfaces import IAgoraSyncedDocument


_PATCH_MARKER = '_collective_agora_original'


def _original_method(owner, name):
    """Return the unwrapped Plone method, including after module reloads."""
    method = getattr(owner, name)
    return getattr(method, _PATCH_MARKER, method)


_query_builder_call = _original_method(QueryBuilder, '__call__')


def _agora_query(self):
    query = _query_builder_call(self)
    context_path = '/'.join(self.context.getPhysicalPath())
    is_agora_page = (
        '/resources/alliance_catalogue_app.' in context_path
        and context_path.count('/') >= 4
    )
    if is_agora_page or IAnnotations(self.context).get('collective.agora.catalogue_path'):
        root = uuidToObject(self.portlet.root_uid)
        if root is not None:
            # The stock navtree query starts at the current document, which
            # intentionally shows only that branch. Agora detail pages need
            # the complete model folder and all of its synced children.
            query['path'] = {'query': '/'.join(root.getPhysicalPath()), 'depth': 1}
    return query


_agora_query.__dict__[_PATCH_MARKER] = _query_builder_call
QueryBuilder.__call__ = _agora_query

_strategy_show_children = _original_method(NavtreeStrategy, 'showChildrenOf')


def _agora_show_children(self, obj):
    if 'alliance_catalogue_app.' in (self.rootPath or ''):
        return True
    return _strategy_show_children(self, obj)


_agora_show_children.__dict__[_PATCH_MARKER] = _strategy_show_children
NavtreeStrategy.showChildrenOf = _agora_show_children

_renderer_get_nav_tree = _original_method(Renderer, 'getNavTree')


def _agora_get_nav_tree(self, _marker=None):
    context_path = '/'.join(self.context.getPhysicalPath())
    if '/resources/alliance_catalogue_app.' not in context_path:
        return _renderer_get_nav_tree(self, _marker)
    root = uuidToObject(self.data.root_uid)
    if root is None:
        return _renderer_get_nav_tree(self, _marker)
    query = QueryBuilder(self.context, self.data)()
    query['path'] = {'query': '/'.join(root.getPhysicalPath()), 'depth': 1}
    strategy = NavtreeStrategy(self.context, self.data)
    strategy.showChildrenOf = lambda obj: True
    # The standard builder intentionally prunes non-folderish roots and is
    # therefore unsuitable for the synced model containers. Build the one
    # level catalogue list directly while retaining Plone's normal node
    # decoration and navigation template.
    root_path = '/'.join(root.getPhysicalPath())
    children = []
    for brain in self.context.portal_catalog(**query):
        if brain.getPath() == root_path:
            continue
        node = {
            'item': brain,
            'depth': 1,
            'currentItem': brain.getPath() == context_path,
            'currentParent': False,
        }
        node = strategy.decoratorFactory(node)
        node['children'] = []
        children.append(node)
    return {'children': children}


_agora_get_nav_tree.__dict__[_PATCH_MARKER] = _renderer_get_nav_tree
Renderer.getNavTree = _agora_get_nav_tree


@adapter(IAgoraSyncedDocument, Interface)
@implementer(INavtreeStrategy)
class AgoraNavtreeStrategy(NavtreeStrategy):
    """Keep the configured catalogue folder expanded in the side tree."""

    def showChildrenOf(self, obj):
        return True
