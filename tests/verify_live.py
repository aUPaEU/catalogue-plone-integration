"""Run inside the Plone container; creates and removes only its own test document."""
import json
import os
import uuid
import requests
from lxml import html

base = 'http://localhost:8080/' + os.environ.get('SITE', 'Plone')
session = requests.Session()
session.auth = ('admin', 'admin')
api = {'Accept': 'application/json'}

def registry(name):
    result = session.get(base + '/@registry/plone.' + name, headers=api)
    result.raise_for_status()
    return result.json()

assert 'agora-component' in registry('valid_tags')
assert all(a in registry('custom_attributes') for a in ('domain', 'url', 'auto-resize'))
assert 'agora' in registry('custom_buttons')
scripts_filtered = (not registry('disable_filtering')
                    and 'script' not in registry('valid_tags'))
templates = json.loads(registry('templates'))
assert sum(t['title'] == 'Agora component' for t in templates) == 1
for asset in ('plugin.js', 'loader.js', 'site.css', 'editor.css'):
    session.get(base + '/++resource++collective.agora/' + asset).raise_for_status()

identifier = 'agora-verification-' + uuid.uuid4().hex
created_url = None
csrf = None
try:
    markup = ('<agora-component domain="https://aupaeu.widening.eu/" '
              'url="/event-catalogue-no-menu" auto-resize="true"></agora-component>'
              '<script>alert("must be filtered")</script>')
    result = session.post(base, headers=api, json={
        '@type': 'Document', 'id': identifier, 'title': 'Temporary Agora verification',
        'text': {'data': markup, 'content-type': 'text/html'},
    })
    result.raise_for_status()
    created_url = result.json()['@id']
    rendered = session.get(created_url)
    rendered.raise_for_status()
    tree = html.fromstring(rendered.text)
    components = tree.xpath('//agora-component')
    assert len(components) == 1
    assert components[0].get('domain') == 'https://aupaeu.widening.eu/'
    assert components[0].get('url') == '/event-catalogue-no-menu'
    assert components[0].get('auto-resize') == 'true'
    if scripts_filtered:
        assert 'must be filtered' not in rendered.text
    assert 'collective.agora/loader.js' in rendered.text
    edit = session.get(created_url + '/edit')
    edit.raise_for_status()
    tree = html.fromstring(edit.text)
    csrf = tree.xpath('//input[@name="_authenticator"]/@value')[0]
    fields = tree.xpath('//*[@data-pat-textareamimetypeselector]')
    assert fields, 'No rich text selector found'
    config = json.loads(fields[0].get('data-pat-textareamimetypeselector'))['widgets']['text/html']['patternOptions']['tiny']
    assert config['external_plugins']['agora'].split('?', 1)[0].endswith('/++resource++collective.agora/plugin.js')
    assert 'agora' in config['toolbar'].split()
    assert 'agora-component' in config['custom_elements']
    assert 'template' in config['plugins']
    assert any(t['title'] == 'Agora component' for t in config['templates'])
    print('PASS: registry, resources, document save/render, HTML filtering and editor configuration')
finally:
    if created_url:
        if csrf:
            session.post(created_url + '/edit', data={
                '_authenticator': csrf, 'form.buttons.cancel': 'Cancel'
            }).raise_for_status()
        result = session.delete(created_url, headers=api)
        result.raise_for_status()
        print('Removed temporary verification document')
