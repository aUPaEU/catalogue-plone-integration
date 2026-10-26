const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname, '../addons/collective.agora/src/collective/agora/static/plugin.js'), 'utf8');
(async function () {
  let dialog, button, attrs, failure = false;
  const actions = [];
  const editor = {
    dom: { getParent: () => null, createHTML: (_, value) => { attrs = value; return '<agora-component></agora-component>'; } },
    selection: { getNode: () => ({}) },
    windowManager: { open: value => { dialog = value; }, alert: text => actions.push('alert') },
    notificationManager: { open: () => {} },
    undoManager: { transact: callback => callback() },
    insertContent: () => actions.push('insert'),
    ui: { registry: { addButton: (_, value) => { button = value; }, addMenuItem: () => {} } },
    on: () => {}
  };
  vm.runInNewContext(source, {
    tinymce: { PluginManager: { add: (_, factory) => factory(editor) } },
    document: { body: { dataset: { portalUrl: 'https://plone.example/Plone1' } }, querySelector: () => null },
    window: { location: { href: 'https://plone.example/Plone1/folder/page/edit', pathname: '/Plone1/folder/page/edit', search: '' } },
    URL, URLSearchParams,
    fetch: async (url, options) => {
      assert.equal(url, 'https://plone.example/Plone1/@@agora-sync');
      const body = JSON.parse(options.body);
      assert.equal(body.model_name, 'alliance_catalogue_app.researchproposals');
      assert.equal(body.source_path, '/folder/page');
      actions.push('fetch');
      return { ok: !failure, json: async () => ({ success: !failure, synced: 2, error: failure ? 'Unavailable' : undefined }) };
    }
  });
  button.onAction();

  const api = { getData: () => ({ domain: 'http://localhost:8010', path: '/research', model: 'alliance_catalogue_app.researchproposals', browserDomain: true }), block: () => {}, unblock: () => {}, close: () => {} };
  await dialog.onSubmit(api);
  assert.deepEqual(actions, ['fetch', 'insert']);
  assert.equal(attrs.sync, 'true');
  assert.equal(attrs['display-domain'], 'browser');
  actions.length = 0;
  failure = true;
  await dialog.onSubmit(api);
  assert.deepEqual(actions, ['fetch', 'alert']);
  console.log('Editor synchronization tests passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
