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
  function wrapButtonLabels() {
    document.querySelectorAll(".button-container .button, .agora-button-container .agora-button").forEach(function (button) {
      // Older templates put the label directly in the button. Wrap it so the
      // catalogue hover/selected pseudo-elements remain behind the label.
      Array.from(button.childNodes).forEach(function (node) {
        if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) return;
        const label = document.createElement("span");
        label.textContent = node.textContent;
        node.replaceWith(label);
      });
    });
  }
  function wireNavigationButtons() {
    wrapButtonLabels();
    const component = document.querySelector("agora-component");
    document.querySelectorAll("[data-agora-url]").forEach(function (button) {
      if (button.dataset.agoraWired === "true") return;
      button.dataset.agoraWired = "true";
      button.addEventListener("click", function (event) {
        const path = button.getAttribute("data-agora-url") || "";
        const model = button.getAttribute("data-agora-model") || "";
        if (!path.startsWith("/") || path.startsWith("//") || /[\\\s\x00-\x1f]/.test(path)) return;
        if (model && !/^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$/.test(model)) return;
        const component = document.querySelector("agora-component");
        if (!component) return;
        event.preventDefault();
        document.querySelectorAll(".button-container .button.selected, .agora-button-container .agora-button.selected")
          .forEach(function (selected) { selected.classList.remove("selected"); });
        button.classList.add("selected");
        button.classList.add("clicked");
        button.addEventListener("animationend", function () {
          button.classList.remove("clicked");
        }, {once: true});
        if (model) component.setAttribute("catalogue-model", model);
        component.setAttribute("url", path);
        // Rebuild the iframe URL so detail_domain and detail_model reflect the
        // selected catalogue before the new view is loaded.
        load();
        if (!model && typeof component.navigateTo === "function") component.navigateTo(path);
      });
    });
    if (component) {
      const currentModel = component.getAttribute("catalogue-model") || "";
      document.querySelectorAll("[data-agora-model]").forEach(function (button) {
        button.classList.toggle("selected", !!currentModel &&
          button.getAttribute("data-agora-model") === currentModel);
      });
    }
  }
  function load() {
    wireNavigationButtons();
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
