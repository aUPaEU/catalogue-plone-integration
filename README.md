# collective.agora

`collective.agora` integrates the Agora catalogue web component with a Plone
site using TinyMCE. Editors can insert an Agora catalogue into page content;
the add-on can also copy catalogue detail pages from an Odoo catalogue API into
Plone documents for local navigation and rendering.

The add-on is installed automatically by the local Compose setup and can also
be installed through the normal Plone add-on mechanism.

## Local setup

From the repository root:

```bash
docker compose up -d
```

Open <http://localhost:8080/Plone1> with the local credentials `admin` / `admin`.
The add-on is installed on the existing or newly created `Plone1` site. The
database is kept in the `plone-data` named volume.

Python changes require a Plone restart; refresh the browser after JavaScript or
CSS changes:

```bash
docker compose restart plone
docker compose logs -f plone
```

`docker compose down` preserves site data. The default image is
`plone/plone-backend:6.2`; `.env.example` documents the version override.

## What the add-on provides

- An **Agora template** button and menu item in TinyMCE.
- A valid/custom `agora-component` element with the required attributes.
- A local loader that fetches the pinned Agora bundle and initializes each
  component after its attributes are present.
- Optional server-side synchronization of Odoo catalogue detail pages into
  `/resources/{catalogue-model}/{item-id}`.
- A Plone detail view for synchronized documents, including imported CSS and
  links back to the catalogue page.
- Navigation support for synchronized catalogue folders.

## Editor workflow

1. Edit a page and choose the `text/html` editor.
2. Select **Agora template** from the TinyMCE toolbar or menu.
3. Enter:
   - **Domain**: the HTTP(S) Odoo origin, for example
     `https://agora.example.org/`.
   - **Path**: the catalogue path, beginning with `/`.
   - **Catalogue model**: the Odoo model, for example
     `alliance_catalogue_app.researchproposals`.
4. Click **Insert**. Existing Agora components can be selected and updated
   with the same dialog.
5. Save and publish the Plone page using the normal workflow.

The editor stores the component configuration in page HTML. The API token is
never placed in page content or exposed to the browser.

The regular **Insert → Template → Agora component** entry is a static starting
point. Use the **Agora template** dialog when synchronization or custom values
are required.

## Configure synchronization

Open **Site Setup → Agora catalogue synchronization** and configure:

- **Odoo catalogue API base URL**: the server-side API root, such as
  `https://odoo.example.org/catalogue-api/v2`.
- **Odoo browser base URL**: the public Odoo origin used in links and asset
  URLs shown to visitors. This is separate from the API URL. In local Docker,
  the API may use `host.docker.internal`, while the browser URL should use
  `localhost` or the public hostname.
- **Odoo catalogue API token**: a bearer token stored in the Plone registry and
  used only by server-side synchronization requests.

When an editor inserts or updates a component, TinyMCE sends a POST request to
`@@agora-sync`. The view creates or updates `/resources/{model}`, fetches every
catalogue page and its HTML detail response, and creates or updates a Plone
Document for each item. Imported styles are preserved separately from editable
content, and existing author content around the synchronized region survives
refreshes.

For a full refresh, send a POST request to `@@agora-sync-all` at the site root.
It scans the site for unique `catalogue-model` attributes and synchronizes each
model. It requires **Manage portal** permission, runs during the request, and
does not provide a scheduler or background job.

```bash
curl -u admin:admin -X POST http://localhost:8080/Plone1/@@agora-sync-all
```

The destination is always based on the model and item ID. The Odoo page URL
does not determine the Plone location. Synchronized documents use the site's
default workflow state; publish them through the normal Plone workflow.

## Permissions and security

- Installing or reapplying the profile requires site administration rights.
- `@@agora-sync` requires `Modify portal content`.
- `@@agora-sync-all` and the settings form require `Manage portal`.
- The API token remains in the Plone registry and is sent only in server-side
  `Authorization: Bearer ...` requests.
- Model names, paths, domains, and detail-navigation IDs are validated before
  use.
- Content-level scripts remain filtered. The profile permits `style` because
  Odoo detail responses can contain embedded CSS.

The remote Odoo site must permit framing. If a reverse proxy adds a Content
Security Policy, allow the Agora bundle source in `script-src`, the Odoo origin
in `frame-src`, and the relevant Odoo/CDN endpoints in `connect-src`.

## Troubleshooting

### The component is missing after saving

Confirm that the add-on profile is installed and that the page uses
`text/html`. The profile adds `agora-component` and its attributes to TinyMCE
and the Plone HTML filter. Close and reopen existing editor sessions after
installation.

### Synchronization fails

Check the API URL from the Plone container, not only from the host browser.
Verify the token, model name, and both the model-list and item HTML endpoints.
The synchronization response is JSON and includes an error when the API fails.

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

- `addons/collective.agora/src/collective/agora/browser.py`: synchronization.
- `views.py`: synchronized-document rendering.
- `detail_fragment.py`: extraction, CSS, and sync-marker helpers.
- `navigation.py`: navigation for synchronized catalogue folders.
- `setuphandlers.py`: idempotent TinyMCE, filter, and resource setup.
- `static/plugin.js`: TinyMCE dialog and synchronization request.
- `static/loader.js`: component loading, resizing, and navigation.

Run the focused checks from the repository root:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_plugin.cjs
node tests/test_loader.cjs
```

The Python tests need the Plone Python environment. The live verification
script is `tests/verify_live.py`; it creates a temporary document, verifies
rendering and editor configuration, then removes the document.

The add-on is idempotent: installing the profile again merges its settings and
preserves existing TinyMCE templates and registry values.
