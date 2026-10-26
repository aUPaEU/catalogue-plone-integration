from zope.component import adapter
from zope.interface import Interface, implementer
from zope.annotation import IAnnotations

from plone.app.portlets.portlets.navigation import (
    INavigationPortlet,
    NavtreeStrategy,
    QueryBuilder,
    Renderer,
)
from plone.app.uuid.utils import uuidToObject
from plone.app.layout.navigation.interfaces import INavtreeStrategy

from .interfaces import IAgoraSyncedDocument


_query_builder_call = QueryBuilder.__call__


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


QueryBuilder.__call__ = _agora_query

_strategy_show_children = NavtreeStrategy.showChildrenOf


def _agora_show_children(self, obj):
    if 'alliance_catalogue_app.' in (self.rootPath or ''):
        return True
    return _strategy_show_children(self, obj)


NavtreeStrategy.showChildrenOf = _agora_show_children

_renderer_get_nav_tree = Renderer.getNavTree


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


Renderer.getNavTree = _agora_get_nav_tree


@adapter(IAgoraSyncedDocument, Interface)
@implementer(INavtreeStrategy)
class AgoraNavtreeStrategy(NavtreeStrategy):
    """Keep the configured catalogue folder expanded in the side tree."""

    def showChildrenOf(self, obj):
        return True
