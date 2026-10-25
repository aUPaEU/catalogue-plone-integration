# Local Plone 6 with Àgora templates

```bash
docker compose up -d
```

Open http://localhost:8080/Plone1 (local credentials: `admin` / `admin`).
The `collective.agora` add-on installs automatically on the existing or newly
created `Plone1` site. The database is kept in the `plone-data` named volume.

Edit a page, choose **text/html**, and click **Àgora template** in TinyMCE.
Enter **Domain** and **Path**, then click **Insert**. Defaults are
`https://aupaeu.widening.eu/` and `/event-catalogue-no-menu`.
Select an existing component and use the same button to update its values.
**Insert → Template → Àgora component** also inserts the default template.

The add-on source is shared through `./addons:/app/addons`. Python changes
require `docker compose restart plone`; refresh the browser after JS/CSS edits.
The install profile preserves existing settings and does not run again on every
restart. See [README-AGORA.md](README-AGORA.md) for configuration and verification.

```bash
docker compose logs -f plone
docker compose down
```

`down` preserves site data. The default image is `plone/plone-backend:6.2`;
`.env.example` documents the version override. The startup script targets this
local FileStorage setup, runs profile installation before the server opens the
database, and never deletes an existing site.
