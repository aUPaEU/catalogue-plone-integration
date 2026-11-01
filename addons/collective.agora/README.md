# collective.agora

`collective.agora` integrates the Agora catalogue web component with a Plone
site using TinyMCE. Editors can insert an Agora catalogue into page content;
the add-on can also copy catalogue detail pages from an Odoo catalogue API into
Plone documents for local navigation and rendering.

The add-on is intended for Plone 6 and is installed through the normal Plone
add-on mechanism. It registers its GenericSetup profile automatically through
the `z3c.autoinclude.plugin` entry point.

## What it provides

- An **Agora template** button and menu item in TinyMCE.
- A valid/custom `agora-component` element with the attributes required by the
  web component.
- A local loader that fetches the pinned Agora bundle and initializes each
  component after its attributes are present.
- Optional server-side synchronization of Odoo catalogue detail pages into
  `/resources/{catalogue-model}/{item-id}`.
- A Plone detail view for synchronized documents, including imported CSS and
  links back to the catalogue page.
- Navigation support for synchronized catalogue folders.

## Requirements

- Plone 6 with `Products.CMFPlone`, `plone.registry`, and
  `plone.app.registry`.
- An Odoo installation exposing the expected catalogue API when synchronization
  is enabled.
- A browser-accessible Odoo origin that allows the catalogue page to be
  embedded in an iframe.

## Editor workflow

1. Edit a page and choose the `text/html` editor.
2. Select **Agora template** from the TinyMCE toolbar or menu.
3. Enter:
   - **Domain**: the HTTP(S) Odoo origin, for example
     `https://agora.example.org/`.
   - **Path**: the catalogue path, beginning with `/`.
   - **Catalogue model**: the Odoo model used by the catalogue, for example
     `alliance_catalogue_app.researchproposals`.
4. Click **Insert**. Existing Agora components can be selected and updated
   with the same dialog.
5. Save and publish the Plone page using the normal workflow.

The editor stores the component configuration in page HTML. The API token is
never placed in page content or exposed to the browser.

The regular TinyMCE **Insert → Template → Agora component** entry is a static
starting point. Use the **Agora template** dialog when synchronization or
custom values are required.

## Configure synchronization

Open **Site Setup → Agora catalogue synchronization** and configure:

- **Odoo catalogue API base URL**: the server-side API root, such as
  `https://odoo.example.org/catalogue-api/v2`.
- **Odoo browser base URL**: the public Odoo origin used in links and asset
  URLs shown to visitors. This is separate from the API URL. In a local Docker
  setup, the API may use `host.docker.internal`, while the browser URL should
  normally use `localhost` or the public hostname.
- **Odoo catalogue API token**: a bearer token stored in the Plone registry and
  used only by server-side synchronization requests.

When an editor inserts or updates a component, TinyMCE sends a POST request to
`@@agora-sync`. The view:

1. Reads the selected model and source page path.
2. Creates or updates `/resources/{model}`.
3. Fetches every catalogue page and its HTML detail response.
4. Creates or updates a Plone Document for each item.
5. Preserves imported styles separately from editable content.

The destination is always based on the model and item ID. The Odoo page URL
does not determine the Plone location. Existing author content around the
synchronized region is preserved between refreshes.

For a full refresh, send a POST request to `@@agora-sync-all` at the site root.
This scans the site for unique `catalogue-model` attributes and synchronizes
each model. It requires the **Manage portal** permission and runs during the
request; the add-on does not provide a scheduler or background job.

Example:

```bash
curl -u admin:admin -X POST \
  https://plone.example.org/Plone1/@@agora-sync-all
```

## Permissions and security

- Installing or reapplying the profile requires site administration rights.
- `@@agora-sync` requires `Modify portal content`.
- `@@agora-sync-all` and the settings form require `Manage portal`.
- The API token remains in the Plone registry and is sent only in server-side
  `Authorization: Bearer ...` requests.
- Model names, paths, domains, and detail-navigation IDs are validated before
  they are used.
- Content-level scripts remain filtered. The profile permits the `style` tag
  because Odoo detail responses can contain embedded CSS.

The remote Odoo site must permit framing. If a reverse proxy adds a Content
Security Policy, allow the required Agora bundle source in `script-src`, the
Odoo origin in `frame-src`, and the relevant Odoo/CDN endpoints in
`connect-src`. The add-on cannot override a stricter policy sent by another
server.

## Troubleshooting

### The component is missing after saving

Confirm that the add-on profile has been installed and that the page is using
`text/html`. The profile adds `agora-component` and its attributes to both the
TinyMCE and Plone HTML-filter configuration. Existing editor sessions may need
to be closed and reopened after installation.

### Synchronization fails

Check the API URL from the Plone container, not only from the host browser.
Verify the token, the model name, and that the Odoo API exposes both the model
list endpoint and each item’s `?response=html` endpoint. The synchronization
response is JSON and includes an error message when the API request fails.

### Detail pages show no styling

Set the browser base URL to an origin reachable by visitors. Relative image and
CSS URLs are resolved against Odoo during synchronization; browser-only
`localhost` or Docker hostnames will not work for remote visitors.

### Auto-resize does not work

Auto-resize depends on the embedded Odoo page sending its height through
`postMessage`. A fixed height or `min-height` can be used as a fallback, but
the remote application must emit resize messages for dynamic sizing.

## Development and verification

The implementation is organized as follows:

- `browser.py`: authenticated catalogue synchronization views.
- `views.py`: synchronized-document rendering.
- `detail_fragment.py`: extraction, CSS handling, and sync-marker helpers.
- `navigation.py`: navigation behavior for synchronized catalogue folders.
- `setuphandlers.py`: idempotent TinyMCE, HTML-filter, and resource setup.
- `static/plugin.js`: TinyMCE dialog and synchronization request.
- `static/loader.js`: browser-side component loading, resizing, and navigation.

Run the focused checks from the repository root:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_plugin.cjs
node tests/test_loader.cjs
```

The Python tests that import Plone packages must run with the Plone Python
environment. The live verification script is `tests/verify_live.py` and uses a
temporary document that it removes after the check.

The add-on is intentionally idempotent: installing the profile again merges
its settings and preserves existing TinyMCE templates and registry values.
