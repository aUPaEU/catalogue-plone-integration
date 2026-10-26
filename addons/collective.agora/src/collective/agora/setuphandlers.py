"""Merge settings so installing twice preserves existing site configuration."""
import json

from plone.base.interfaces.controlpanel import IFilterSchema, ITinyMCESchema
from plone.base.interfaces.resources import IBundleRegistry
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from .interfaces import IAgoraSyncSettings, ensure_settings_registry

TEMPLATE = {
    "title": "Àgora component",
    "description": "Insert Agora, then use the Àgora template button to edit domain and path.",
    "content": '<agora-component domain="https://aupaeu.widening.eu/" '
               'url="/event-catalogue-no-menu" auto-resize="true" sync="false" '
               'display-domain="odoo"></agora-component>',
}


def append_unique(values, additions):
    return list(dict.fromkeys(list(values or []) + additions))


def install(context):
    registry = getUtility(IRegistry)
    ensure_settings_registry(registry)
    filters = registry.forInterface(IFilterSchema, prefix="plone")
    # Odoo detail responses include embedded CSS.  Keep style elements in the
    # editable RichTextValue; executable script elements remain filtered.
    # Remove a legacy installation's broad script allow-list. The Agora
    # loader is installed as a resource and the paste handler removes only
    # its old bootstrap snippet; page content must not persist arbitrary
    # executable scripts.
    filters.valid_tags = [tag for tag in (filters.valid_tags or []) if tag != "script"]
    filters.valid_tags = append_unique(filters.valid_tags, ["agora-component", "style", "button"])
    # Plone's HTML filter has a separate denylist for tags considered unsafe.
    # Remove only style from that list; scripts and the other unsafe tags stay
    # blocked.
    filters.nasty_tags = [tag for tag in (filters.nasty_tags or []) if tag != "style"]
    filters.custom_attributes = append_unique(
        filters.custom_attributes, ["domain", "url", "auto-resize", "sync", "catalogue-model", "sync-parent", "display-domain", "media", "type", "data-agora-url", "data-agora-model"]
    )
    tiny = registry.forInterface(ITinyMCESchema, prefix="plone")
    tiny.custom_plugins = [p for p in (tiny.custom_plugins or [])
                           if p.split("|", 1)[0] != "agora"] + [
        "agora|++resource++collective.agora/plugin.js?v=9"
    ]
    tiny.custom_buttons = append_unique(tiny.custom_buttons, ["agora"])
    tiny.plugins = append_unique(tiny.plugins, ["template"])
    templates = json.loads(tiny.templates or "[]")
    if templates == {}:
        templates = []
    if not isinstance(templates, list):
        raise ValueError("TinyMCE templates must be a JSON list before installing Agora")
    if not any(t.get("title") == TEMPLATE["title"] for t in templates):
        templates.append(TEMPLATE)
    tiny.templates = json.dumps(templates, ensure_ascii=False)
    options = json.loads(tiny.other_settings or "{}")
    custom = options.get("custom_elements", "")
    if isinstance(custom, dict):
        custom.setdefault("agora-component", {"extends": "div"})
    else:
        custom = ",".join(append_unique(
            [x.strip() for x in custom.split(",") if x.strip()], ["agora-component"]
        ))
    options["custom_elements"] = custom
    extended = options.get("extended_valid_elements", "")
    options["extended_valid_elements"] = ",".join(append_unique(
        [x for x in extended.split(",") if x],
        ["agora-component[domain|url|auto-resize|sync|catalogue-model|sync-parent|display-domain|class|style]", "style[type|media]", "button[class|type|data-agora-url|data-agora-model]", "a[class|data-agora-url|data-agora-model]"]
    ))
    # TinyMCE settings persist across profile upgrades, so explicitly retain
    # the security boundary even when an older profile had enabled scripts.
    options["invalid_elements"] = ",".join(append_unique(
        [x.strip() for x in options.get("invalid_elements", "").split(",") if x.strip()],
        ["script"]
    ))
    # TinyMCE otherwise treats style as a head-only element and drops it when
    # the editor body is parsed, even though the tag is in valid_elements.
    options["valid_children"] = ",".join(append_unique(
        [x.strip() for x in options.get("valid_children", "").split(",") if x.strip()],
        ["+body[style]"]
    ))
    tiny.other_settings = json.dumps(options)
    tiny.content_css = append_unique(tiny.content_css, [
        "++resource++collective.agora/editor.css"
    ])
    prefix = "plone.bundles/collective-agora"
    registry.registerInterface(IBundleRegistry, prefix=prefix)
    bundle = registry.forInterface(IBundleRegistry, prefix=prefix)
    bundle.enabled = True
    bundle.jscompilation = "++resource++collective.agora/loader.js"
    bundle.csscompilation = "++resource++collective.agora/site.css"
    bundle.load_defer = True
    bundle.depends = "plone"
    bundle.compile = False

    # This older manual bundle bypasses the loader's attribute preparation.
    legacy_js = registry.records.get("plone.bundles/agora.jscompilation")
    legacy_enabled = registry.records.get("plone.bundles/agora.enabled")
    if legacy_js is not None and legacy_enabled is not None:
        if legacy_js.value == "https://cdn.jsdelivr.net/gh/KinoGlazPrusia/agora-component@v1.0.0/dist/agora-bundle.js":
            legacy_enabled.value = False
