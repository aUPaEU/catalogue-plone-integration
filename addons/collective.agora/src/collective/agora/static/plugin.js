/* global tinymce */
(function () {
  "use strict";
  tinymce.PluginManager.add("agora", function (editor) {
    // The legacy embed instructions include a script which creates the Agora
    // bundle tag. Plone intentionally filters arbitrary scripts, and the
    // installed loader already loads that bundle. Remove only this recognized
    // bootstrap when it is pasted together with an Agora component; leave all
    // other pasted content to TinyMCE's normal filtering.
    function decodeEscapedMarkup(content) {
      if (!/&lt;\s*agora-component\b/i.test(content || "")) return content;
      const textarea = document.createElement("textarea");
      textarea.innerHTML = content;
      return textarea.value;
    }

    function normalizePastedContent(content) {
      let normalized = content || "";
      // Some copy/paste sources escape every opening tag as \<tag>. Restrict
      // this repair to Agora markup so ordinary prose containing backslashes
      // is left unchanged.
      if (/\\<\s*agora-component\b/i.test(normalized)) {
        normalized = normalized.replace(/\\(?=<)/g, "");
      }
      const decoded = decodeEscapedMarkup(normalized);
      if (!/<agora-component\b/i.test(decoded || "")) return content;
      return decoded.replace(
        /<script\b[^>]*>[\s\S]*?<\/script\s*>/gi,
        function (script) {
          return /agora-bundle|createElement\s*\(\s*["']script["']\s*\)/i.test(script)
            ? ""
            : script;
        }
      ).replace(
        /(<(?:button|a)\b[^>]*?)\s+onclick\s*=\s*["']\s*navigateTo\(\s*["']([^"']+)["']\s*\)["']/gi,
        function (_, prefix, path) {
          return prefix + ' data-agora-url="' + path.replace(/&/g, "&amp;").replace(/"/g, "&quot;") + '"';
        }
      );
    }

    editor.on("PastePreProcess", function (event) {
      event.content = normalizePastedContent(event.content);
    });
    editor.on("BeforeSetContent", function (event) {
      event.content = normalizePastedContent(event.content);
    });

    function getSiteUrl() {
      const portalUrl = document.body.dataset.portalUrl || window.PORTAL_URL;
      if (portalUrl) return new URL(portalUrl, window.location.href).href.replace(/\/$/, "");
      const base = document.querySelector("base");
      if (base && base.href) return new URL(base.href, window.location.href).href.replace(/\/$/, "");
      const parts = window.location.pathname.split("/").filter(Boolean);
      return window.location.origin + (parts.length ? "/" + parts[0] : "");
    }

    function getAuthenticator() {
      const input = document.querySelector('input[name="_authenticator"]');
      if (input && input.value) return input.value;
      return new URLSearchParams(window.location.search).get("_authenticator") || "";
    }

    function getContentPath() {
      const siteUrl = new URL(getSiteUrl());
      const pathname = window.location.pathname.split("?", 1)[0].split("#", 1)[0];
      const sitePath = siteUrl.pathname.replace(/\/$/, "");
      let contentPath = pathname.startsWith(sitePath) ? pathname.slice(sitePath.length) : pathname;
      contentPath = contentPath.replace(/\/edit\/?$/, "");
      return contentPath || "/";
    }

    function openDialog() {
      const selected = editor.dom.getParent(editor.selection.getNode(), "agora-component");
      editor.windowManager.open({
        title: "Agora template",
        body: { type: "panel", items: [
          { type: "input", name: "domain", label: "Domain" },
          { type: "input", name: "path", label: "Path" },
          { type: "input", name: "model", label: "Catalogue model (for synchronization)" }
        ] },
        initialData: {
          domain: selected ? selected.getAttribute("domain") : "https://aupaeu.widening.eu/",
          path: selected ? selected.getAttribute("url") : "/event-catalogue-no-menu",
          model: selected ? selected.getAttribute("catalogue-model") : ""
        },
        buttons: [
          { type: "cancel", text: "Cancel" },
          { type: "submit", text: selected ? "Update" : "Insert", primary: true }
        ],
        onSubmit: async function (api) {
          const data = api.getData();
          let domain;
          const path = data.path.trim();
          try {
            domain = new URL(data.domain.trim());
            if (!["https:", "http:"].includes(domain.protocol) || domain.username ||
                domain.password || domain.pathname !== "/" || domain.search || domain.hash) {
              throw new Error("Invalid domain");
            }
            if (!path.startsWith("/") || path.startsWith("//") || /[\\\s\x00-\x1f]/.test(path)) {
              throw new Error("Invalid path");
            }
          } catch (_) {
            editor.windowManager.alert("Enter an HTTP(S) domain and a path starting with a single /.");
            return;
          }
          if (!data.model.trim()) {
            editor.windowManager.alert("Enter the Odoo catalogue model to synchronize.");
            return;
          }
          const detailUrl = new URL(path, domain.origin).href.slice(domain.origin.length);
          const attrs = {
            domain: domain.origin,
            url: detailUrl,
            "auto-resize": "true",
            sync: "true",
            "catalogue-model": data.model.trim(),
            "sync-parent": "resources",
            "display-domain": "browser"
          };
          api.block("Synchronizing catalogue…");
          try {
            const siteUrl = getSiteUrl();
            const csrfToken = getAuthenticator();
            const response = await fetch(siteUrl + "/@@agora-sync", {
              method: "POST",
              credentials: "same-origin",
              headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                ...(csrfToken ? { "X-CSRF-TOKEN": csrfToken } : {})
              },
              body: JSON.stringify({
                model_name: data.model.trim(),
                source_path: getContentPath()
              })
            });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Synchronization failed");
            editor.notificationManager.open({ text: `Synchronized ${result.synced} catalogue pages.`, type: "success" });
          } catch (error) {
            api.unblock();
            editor.windowManager.alert(error.message || "Catalogue synchronization failed.");
            return;
          }
          api.unblock();
          editor.undoManager.transact(function () {
            if (selected) {
              editor.dom.setAttribs(selected, attrs);
              editor.nodeChanged();
            } else {
              editor.insertContent(editor.dom.createHTML("agora-component", attrs, "") + "<p></p>");
            }
          });
          api.close();
        }
      });
    }
    editor.ui.registry.addButton("agora", { text: "Agora template", onAction: openDialog });
    editor.ui.registry.addMenuItem("agora", { text: "Agora template", onAction: openDialog });
    editor.on("DblClick", function (event) {
      if (editor.dom.getParent(event.target, "agora-component")) openDialog();
    });
    return { getMetadata: function () { return { name: "Agora template" }; } };
  });
}());
