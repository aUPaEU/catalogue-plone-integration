(function () {
  "use strict";
  const source = "https://cdn.jsdelivr.net/gh/KinoGlazPrusia/agora-component@v1.0.0/dist/agora-bundle.js";
  function getPloneSiteUrl() {
    const portalUrl = document.body.dataset.portalUrl || window.PORTAL_URL;
    if (portalUrl) return new URL(portalUrl, window.location.href).href.replace(/\/$/, "");
    const base = document.querySelector("base");
    if (base && base.href) {
      const baseUrl = new URL(base.href, window.location.href);
      return baseUrl.origin + baseUrl.pathname.replace(/\/$/, "");
    }
    const firstPath = window.location.pathname.split("/").filter(Boolean)[0];
    return firstPath ? window.location.origin + "/" + firstPath : window.location.origin;
  }

  function usesPloneDetails(element) {
    return element.getAttribute("sync") === "true" ||
      element.getAttribute("display-domain") === "browser";
  }

  // Only the configured catalogue iframe may request navigation. Construct the
  // destination here instead of accepting a URL supplied through postMessage.
  window.addEventListener("message", function (event) {
    const data = event.data;
    if (!data || data.type !== "agora-open-detail" || !/^\d+$/.test(String(data.elementId))) return;
    for (const element of document.querySelectorAll("agora-component")) {
      if (!usesPloneDetails(element)) continue;
      const iframe = element.shadowRoot && element.shadowRoot.querySelector("iframe");
      if (!iframe || iframe.contentWindow !== event.source) continue;
      try {
        if (event.origin !== new URL(element.getAttribute("domain")).origin) return;
        const model = element.getAttribute("catalogue-model") || "";
        if (!/^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$/.test(model)) return;
        window.location.assign(getPloneSiteUrl() + "/resources/" +
          encodeURIComponent(model) + "/" + encodeURIComponent(data.elementId));
      } catch (_) {
        console.error("Invalid Agora detail navigation configuration");
      }
      return;
    }
  });

  const preparedFrames = new WeakMap();
  function load() {
    if (!document.querySelector("agora-component")) return;
    // The upstream constructor reads attributes immediately and interpolates them
    // into iframe markup. Normalize all elements before registering the component.
    document.querySelectorAll("agora-component").forEach(function (element) {
      try {
        const domain = new URL(element.getAttribute("domain"));
        const path = element.getAttribute("url") || "/";
        const target = new URL(path, domain.origin);
        if (!["http:", "https:"].includes(domain.protocol) || domain.username ||
            domain.password || target.origin !== domain.origin ||
            !path.startsWith("/") || path.startsWith("//")) throw new Error("Invalid Agora URL");
        element.setAttribute("domain", domain.origin);
        element.setAttribute("url", target.href.slice(domain.origin.length));
        if (usesPloneDetails(element)) {
          const iframeUrl = new URL(target.href);
          iframeUrl.searchParams.set("detail_domain", getPloneSiteUrl());
          iframeUrl.searchParams.set("detail_model", element.getAttribute("catalogue-model") || "");
          element.setAttribute("url", iframeUrl.href.slice(domain.origin.length));
        }
        // Plone may insert or replace content after the custom element has
        // registered. Its constructor has already built an iframe in that case.
        const configuredUrl = element.getAttribute("url");
        const iframe = element.shadowRoot && element.shadowRoot.querySelector("iframe");
        if (iframe) {
          const expected = domain.origin + configuredUrl;
          if (preparedFrames.get(iframe) !== expected) {
            element.domain = domain.origin;
            element.url = configuredUrl;
            if (iframe.src !== expected) iframe.src = expected;
            preparedFrames.set(iframe, expected);
          }
        }
      } catch (_) {
        const message = document.createElement("p");
        message.textContent = "Invalid Agora domain or path. Edit the Àgora template to correct it.";
        element.replaceWith(message);
      }
    });
    if (customElements.get("agora-component") ||
        document.querySelector('script[src="' + source + '"]')) return;
    const script = document.createElement("script");
    script.src = source;
    script.async = true;
    script.addEventListener("error", function () {
      console.error("Unable to load the Agora component bundle:", source);
    });
    document.head.appendChild(script);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
  new MutationObserver(load).observe(document.documentElement, { childList: true, subtree: true });
}());
