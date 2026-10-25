# Àgora add-on: automatic setup

The implementation lives in `addons/collective.agora` and is installed in editable
mode from the shared Docker bind mount. Run `docker compose up -d`; installation
also applies to the existing `Plone1` site, without replacing its contents.

## Use

1. Edit a page and select the `text/html` editor.
2. Click **Àgora template** in the toolbar.
3. Fill **Domain** (HTTP/HTTPS origin), **Path** (starting with `/`), and **Catalogue model** (e.g. `alliance_catalogue_app.researchproposals`).
4. Insert and save. Auto-resize is enabled automatically.

The same button updates the selected component. TinyMCE displays a labelled
placeholder; the saved page runs the real web component. The regular
**Insert → Template** menu also contains **Àgora component** with the defaults.

## What installation configures

- TinyMCE plugin, toolbar button, default template and editor placeholder CSS.
- `agora-component` as a custom/valid element, with `domain`, `url`, `auto-resize`.
- The matching Plone HTML filter allowlist additions.
- A deferred local loader and display CSS in Plone's resource registry.

## Catalogue synchronization

In **Site Setup → Àgora catalogue synchronization**, configure the Odoo v2
catalogue API base URL and its JWT bearer token. The token is stored in Plone's
registry and is used only by the authenticated server-side `@@agora-sync` view;
it is never written into page HTML or sent by the browser.

When Plone runs in Docker and Odoo runs on the host, do not use `localhost` in
the API URL. Use `http://host.docker.internal:8010/catalogue-api/v2`; the local
Compose configuration maps this name to the Docker host. If Odoo is another
container, use its Docker service hostname instead.

Inserting or updating through **Àgora template** automatically synchronizes the
catalogue before inserting the component. Plone fetches every page of the JSON
catalogue and each item's `/catalogue-api/v2/{model}/{id}?response=html` response.
Documents are created or updated at `/resources/{model}/{id}` relative to the
Plone site, for example `/Plone1/resources/alliance_catalogue_app.researchproposals/3`.
Legacy parent-path settings and Odoo `/offering/` paths no longer determine the destination.
Existing pages at old paths are left in place; update the component to create the new pages.

Embedded CSS from the HTML response is preserved, including media attributes.
Relative image and CSS asset URLs resolve against Odoo. Older responses with
stylesheet links remain supported. Created documents use the site's default
workflow state; publish them using the normal Plone workflow when ready.

**Use this Plone site for detail links** defaults to enabled for new components.
It passes `detail_domain` and `detail_model` to the embedded Odoo catalogue.
The static Insert → Template shortcut is a placeholder; configure it using the
**Àgora template** button to synchronize its catalogue.

The loader loads the requested v1.0.0 bundle once, after component attributes
exist. It normalizes the origin and path before registration to avoid doubled
slashes and unsafe iframe attribute interpolation in the upstream bundle.
The component stays at the insertion point in page content, supporting multiple
embeds. JavaScript executes through registered resources; content-level scripts
remain filtered and HTML filtering stays enabled.

## Permissions and CSP

Installation needs site administration rights. Authors with existing page editing
rights can insert a component. No new global JavaScript execution permission is
needed for content authors.

This local Plone service currently sends no CSP header, so no CSP modification is
required. If a reverse proxy adds a policy, merge these sources into that policy:

- `script-src`: `'self'` and `https://cdn.jsdelivr.net`.
- `connect-src`: `https://cdn.jsdelivr.net` (the upstream bundle fetches its CSS).
- `frame-src`: each allowed Agora domain.
- `style-src`: the component injects an inline shadow-root style; the upstream
  bundle needs a policy allowing that style (or a CSP-compatible upstream change).

A Plone add-on cannot override a stricter CSP or frame policy sent by another
server. The selected remote site must permit embedding. Auto-resize depends on
messages emitted by that remote application. Although JavaScript is pinned to
v1.0.0, that upstream version fetches its CSS from `@main`.

## Verification

Run against the local default admin account:

```bash
docker compose exec -T plone /app/bin/python < tests/test_setup.py
docker compose exec -T plone /app/bin/python < tests/verify_live.py
```

Regression checks (the Python tests need the Plone environment):

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_plugin.cjs
```

After deploying the updated add-on, restart Plone; the startup installer applies
profile version 1003 to refresh the editor and loader resources. Deploy the two
updated JavaScript files in Odoo's `website_general_list_app` and rebuild its
frontend assets. Odoo navigation can be checked with
`node addons/website_general_list_app/tests/test_plone_navigation.cjs`.

The integration check creates a uniquely named temporary document, verifies
rendered HTML, filtering, resource delivery and editor configuration, then cancels
the edit lock and removes that document. The setup test checks merging and repeat
installation against an in-memory registry.

The automatic install targets `SITE` (`Plone1` in Compose). To install the package
on another site in this Zope container, use that site's **Site Setup → Add-ons →
Agora TinyMCE templates**. To reapply settings intentionally, import
`collective.agora:default` through GenericSetup; normal restarts preserve changes
made after installation.

---

The following notes describe the previous manual setup. The add-on above now
performs the editor, filtering and resource configuration automatically.

# Integrar el webcomponent Àgora a Plone 6

## 1. Carregar el bundle des de la interfície

Entra com a administrador i obre:

```text
http://localhost:8080/Plone1/@@resourceregistry-controlpanel
```

A **Añadir nuevo paquete**, configura:

```text
Nombre: agora
JavaScript: https://cdn.jsdelivr.net/gh/KinoGlazPrusia/agora-component@v1.0.0/dist/agora-bundle.js
CSS: deixar buit
Activado: marcat
Condición: deixar buit
Depende de: plone
Async: desmarcat
Defer: marcat
```

Prem **Añadir**, desa els canvis i fes **Build/Compilar** si Plone ho demana.

Comprova que el bundle s’ha carregat amb la consola del navegador:

```js
document.querySelector('script[src*="agora-bundle.js"]')
```

Si retorna un element `script`, el bundle està carregat.

## 2. Configurar la plantilla TinyMCE

La plantilla no ha de contenir cap `<script>`. Ha de contenir el custom element:

```json
[
  {
    "title": "Àgora component",
    "description": "Insereix un webcomponent Àgora",
    "content": "<div class=\"agora-component-wrapper\"><agora-component domain=\"https://aupaeu.widening.eu/\" url=\"/event-catalogue-no-menu\" auto-resize=\"true\"></agora-component></div>"
  }
]
```

Després d’actualitzar la plantilla:

1. Elimina el contingut antic de la pàgina.
2. Insereix de nou la plantilla.
3. Desa i publica la pàgina.
4. Fes una recàrrega completa amb `Ctrl + Shift + R`.

## 3. Si només apareix aquest `div`

Si el codi publicat és només:

```html
<div class="agora-component-wrapper"></div>
```

vol dir que Plone ha eliminat l’etiqueta `<agora-component>` mitjançant el filtratge HTML, o bé que aquesta etiqueta no forma part del contingut de la plantilla.

Per saber quin filtre actua, insereix la plantilla i obre el selector `text/html`
de l’editor abans de desar:

- Si `<agora-component>` ja no hi és dins de l’editor, TinyMCE l’ha eliminat.
- Si hi és dins de l’editor però desapareix després de desar, l’ha eliminat el
  filtratge HTML de Plone.

Ves a:

```text
Admin → Site Setup → Security → HTML Filtering
```

Afegeix a **Valid tags**:

```text
agora-component
```

Afegeix a **Custom attributes** o **Valid attributes**:

```text
domain
url
auto-resize
```

Desa la configuració i torna a inserir la plantilla.

Si TinyMCE continua eliminant l’etiqueta abans de desar, ves a:

```text
Admin → Site Setup → TinyMCE → Advanced
```

Al camp **Other settings JSON**, afegeix aquesta configuració:

```json
{
  "custom_elements": "agora-component",
  "extended_valid_elements": "agora-component[domain|url|auto-resize]"
}
```

Si ja hi ha altres opcions JSON, conserva-les i afegeix aquesta propietat
dins del mateix objecte. `custom_elements` és necessari perquè TinyMCE
reconegui `agora-component` com un element HTML personalitzat abans d’aplicar
`extended_valid_elements`.

Desa la configuració, tanca i torna a obrir l’editor, i insereix la plantilla
de nou. No n’hi ha prou amb refrescar només la pàgina d’edició si TinyMCE ja
estava obert.

El resultat esperat al codi font és:

```html
<div class="agora-component-wrapper">
  <agora-component
    domain="https://aupaeu.widening.eu/"
    url="/event-catalogue-no-menu"
    auto-resize="true">
  </agora-component>
</div>
```

## 4. CSP

Si el navegador mostra errors de Content Security Policy, el servidor ha de permetre:

```text
script-src https://cdn.jsdelivr.net
frame-src https://aupaeu.widening.eu
```

La CSP no es configura dins de la plantilla TinyMCE. S’ha d’afegir al reverse proxy, Nginx, Apache, Cloudflare o servidor que publiqui Plone.

## 5. Si `auto-resize` no ajusta l’alçada

Els missatges de la consola relacionats amb cookies de Matomo no són errors
del webcomponent. Per comprovar el component, executa:

```js
const agora = document.querySelector('agora-component');
agora.getAttribute('auto-resize');
agora.getBoundingClientRect();
```

El resultat de la primera línia ha de ser `true` i l’element ha d’existir.

`auto-resize` només pot funcionar si la pàgina carregada dins del component
envia la seva alçada al webcomponent mitjançant `postMessage`. Com que
`https://aupaeu.widening.eu` és un domini diferent del domini de Plone, Plone
no pot calcular directament l’alçada del seu contingut. Si la pàgina Àgora no
envia aquest missatge, el component es queda amb una alçada fixa i mostra una
barra de desplaçament interna.

Per confirmar-ho, prova temporalment una alçada fixa a la plantilla:

```html
<agora-component
  domain="https://aupaeu.widening.eu/"
  url="/event-catalogue-no-menu"
  auto-resize="true"
  style="display:block; width:100%; height:1200px;">
</agora-component>
```

Si amb aquesta alçada el contingut es veu complet, el bundle funciona i el
problema és la comunicació de l’auto-resize amb la pàgina remota. En aquest
cas, cal que l’aplicació Àgora implementi el `postMessage` de resize o utilitzar
una alçada fixa/min-height com a alternativa.

## 6. Diferència respecte de la integració antiga

La integració antiga era diferent en dos punts importants:

```js
const agoraScript = document.createElement('script');
agoraScript.src = 'https://cdn.jsdelivr.net/gh/KinoGlazPrusia/agora-component@v1.0.0/dist/agora-bundle.js';
document.head.append(agoraScript);

const agora = document.createElement('agora-component');
agora.setAttribute('domain', 'https://aupaeu.widening.eu/');
agora.setAttribute('url', '/event-catalogue-no-menu');
agora.setAttribute('auto-resize', true);
agora.style.display = 'block';

document.querySelector('#content-core').appendChild(agora);
```

1. El component es crea i rep els atributs **abans que el bundle acabi de
   carregar-se**. Això permet que el navegador l’actualitzi quan el bundle
   registra `agora-component`.
2. S’insereix directament dins de `#content-core`, sense un wrapper intermedi.

La configuració actual del Resource Registry carrega el bundle abans de crear
el component. Si després es fa `document.createElement('agora-component')`, el
constructor del bundle pot executar-se abans que `domain` i `url` s’hagin
assignat. A més, un wrapper pot afectar el càlcul de l’amplada o l’alçada.

Per reproduir el comportament antic, mantén el bundle carregat globalment però
fes que la plantilla s’insereixi directament a `#content-core`. Si el bundle
requereix que el component existeixi abans del registre, caldrà un petit loader
personalitzat que creï el component abans de carregar el bundle.
