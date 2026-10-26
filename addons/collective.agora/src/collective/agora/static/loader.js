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

  // The upstream bundle's resize listener is global and can attach to only
  // the first component on pages containing several catalogues. Keep the
  // resize handling local to each iframe so every catalogue can report its
  // own height. The source check is essential because the message crosses an
  // origin boundary.
  const resizeFrames = new WeakSet();
  function wireAutoResize(element, iframe, origin) {
    const resizeAttribute = element.getAttribute("auto-resize");
    const resizeEnabled = (typeof element.hasAttribute === "function" &&
      element.hasAttribute("auto-resize")) && resizeAttribute !== "false";
    if (!iframe || !resizeEnabled || resizeFrames.has(iframe)) return;
    resizeFrames.add(iframe);
    window.addEventListener("message", function (event) {
      let data = event.data;
      if (typeof data === "string") {
        try { data = JSON.parse(data); } catch (_) { return; }
      }
      if (!data || typeof data !== "object") return;
      if (event.origin !== origin) return;
      // Agora identifies each iframe with the numeric name/context id. Use it
      // alongside source matching so messages from all component instances are
      // handled even when the browser does not expose the nested source window
      // consistently.
      const iframeId = iframe.getAttribute && iframe.getAttribute("name");
      const sameSource = event.source === iframe.contentWindow;
      const sameContext = iframeId && data.id != null && String(data.id) === String(iframeId);
      if (!sameSource && !sameContext) return;
      const type = String(data.type || data.event || data.action || "").toLowerCase();
      if (type && !/(?:resize|height)/.test(type)) return;
      const payload = data.detail || data.payload || data.data || data;
      const value = payload.height != null ? payload.height :
        (payload.iframeHeight != null ? payload.iframeHeight : payload.value);
      const height = typeof value === "number" ? value :
        (typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value.trim()) ? Number(value) : NaN);
      if (!Number.isFinite(height) || height < 1 || height > 100000) return;
      iframe.style.height = Math.ceil(height) + "px";
      element.style.height = Math.ceil(height) + "px";
    });
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
      if (!button || !button.childNodes) return;
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
  function selectComponent(model) {
    const components = Array.from(document.querySelectorAll("agora-component"));
    if (!components.length) return null;
    const selected = components.find(function (element) {
      return !model || element.getAttribute("catalogue-model") === model;
    }) || components[0];
    const wasHidden = selected.hidden === true;
    components.forEach(function (element) {
      element.hidden = element !== selected;
    });
    // A hidden iframe reports a zero/viewport-sized document to Agora. Reload
    // it when it is first revealed so the remote catalogue recalculates its
    // height at the visible width and emits its resize message again.
    if (wasHidden) {
      const iframe = selected.shadowRoot && selected.shadowRoot.querySelector("iframe");
      if (iframe && iframe.src) iframe.src = iframe.src;
    }
    return selected;
  }
  function wireNavigationButtons() {
    wrapButtonLabels();
    const component = document.querySelector("agora-component");
    document.querySelectorAll("[data-agora-url]").forEach(function (button) {
      if (!button || !button.dataset || typeof button.addEventListener !== "function") return;
      if (button.dataset.agoraWired === "true") return;
      button.dataset.agoraWired = "true";
      button.addEventListener("click", function (event) {
        const path = button.getAttribute("data-agora-url") || "";
        const model = button.getAttribute("data-agora-model") || "";
        if (!path.startsWith("/") || path.startsWith("//") || /[\\\s\x00-\x1f]/.test(path)) return;
        if (model && !/^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$/.test(model)) return;
        const components = Array.from(document.querySelectorAll("agora-component"));
        const component = components.find(function (element) {
          return !model || element.getAttribute("catalogue-model") === model;
        }) || components[0];
        if (!component) return;
        event.preventDefault();
        document.querySelectorAll(".button-container .button.selected, .agora-button-container .agora-button.selected")
          .forEach(function (selected) { selected.classList.remove("selected"); });
        button.classList.add("selected");
        button.classList.add("clicked");
        button.addEventListener("animationend", function () {
          button.classList.remove("clicked");
        }, {once: true});
        if (!components.includes(component) || !model) return;
        selectComponent(model);
      });
    });
    if (component) {
      const currentModel = component.getAttribute("catalogue-model") || "";
      document.querySelectorAll("[data-agora-model]").forEach(function (button) {
        if (!button || !button.classList) return;
        button.classList.toggle("selected", !!currentModel &&
          button.getAttribute("data-agora-model") === currentModel);
      });
      selectComponent(currentModel);
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
          wireAutoResize(element, iframe, domain.origin);
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
    // Existing <agora-component> elements are upgraded when this script
    // registers the custom element, without a childList mutation. Run the
    // normalization pass again after registration so every shadow iframe gets
    // its URL and resize listener.
    script.addEventListener("load", load);
    script.addEventListener("error", function () {
      console.error("Unable to load the Agora component bundle:", source);
    });
    document.head.appendChild(script);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
  new MutationObserver(load).observe(document.documentElement, { childList: true, subtree: true });
}());
