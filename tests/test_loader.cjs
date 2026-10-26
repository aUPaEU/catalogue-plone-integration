const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = process.argv[2] || path.join(__dirname, '../addons/collective.agora/src/collective/agora/static/loader.js');
let message, load;
let registered = true;
const iframe = { contentWindow: {}, src: "http://odoo.example/courses" };
const destinations = [];
const iframeWindow = iframe.contentWindow;
const attrs = { domain: 'http://odoo.example', url: '/courses', sync: 'true', 'display-domain': 'odoo', 'catalogue-model': 'alliance_catalogue_app.course' };
const element = { getAttribute: name => attrs[name], setAttribute: (name, value) => { attrs[name] = value; }, shadowRoot: { querySelector: () => iframe } };
vm.runInNewContext(fs.readFileSync(file, 'utf8'), {
  window: { location: { href: 'https://plone.example/Plone1/catalogue', assign: url => destinations.push(url) }, addEventListener: (_, handler) => { message = handler; } },
  document: {
    body: { dataset: { portalUrl: 'https://plone.example/Plone1' } },
    readyState: 'loading', addEventListener: (_, handler) => { load = handler; },
    querySelector: selector => selector === 'agora-component' ? element : null,
    querySelectorAll: () => [element],
    createElement: () => ({ addEventListener: () => {} }), head: { appendChild: () => {} }, documentElement: {}
  },
  customElements: { get: () => registered ? function Agora() {} : undefined }, MutationObserver: class { observe() {} }, URL, console
});
load();
const url = new URL(attrs.url, attrs.domain);
assert.equal(url.searchParams.get('detail_domain'), 'https://plone.example/Plone1');
assert.equal(url.searchParams.get('detail_model'), 'alliance_catalogue_app.course');
assert.equal(iframe.src, url.href, 'Already registered components must get the configured URL');
// Repeated observer callbacks must not reset an iframe after a user navigates.
iframe.src = 'http://odoo.example/some-other-page';
load();
assert.equal(iframe.src, 'http://odoo.example/some-other-page');
const event = { data: { type: 'agora-open-detail', elementId: '3', url: 'https://untrusted.example' }, origin: attrs.domain, source: iframeWindow };
message(event);
assert.deepEqual(destinations, ['https://plone.example/Plone1/resources/alliance_catalogue_app.course/3']);
message({ ...event, origin: 'https://untrusted.example' });
message({ ...event, source: {} });
message({ ...event, data: { type: 'agora-open-detail', elementId: '../escape' } });
assert.equal(destinations.length, 1);
console.log('Plone parent navigation and source validation tests passed');
