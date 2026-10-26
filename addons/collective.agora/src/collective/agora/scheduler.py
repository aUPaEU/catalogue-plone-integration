"""Process-local scheduler for automatic catalogue synchronization."""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime

import transaction
from Zope2 import app as open_app
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.hooks import setSite

from .browser import AgoraSyncView
from .interfaces import IAgoraSyncSettings, ensure_settings_registry

logger = logging.getLogger(__name__)
_MODEL = re.compile(r'\bcatalogue-model\s*=\s*["\']([^"\']+)', re.I)
_started = False


class _Response:
    def setStatus(self, status):
        self.status = status

    def setHeader(self, name, value):
        pass


class _Request:
    method = 'POST'

    def __init__(self, payload):
        self.response = _Response()
        self._body = json.dumps(payload)

    def get(self, name, default=None):
        return self._body if name == 'BODY' else default


def _models(site):
    found = set()

    def walk(folder):
        for child in folder.objectValues():
            text = getattr(child, 'text', None)
            raw = getattr(text, 'raw', '') if text else ''
            found.update(_MODEL.findall(raw or ''))
            if hasattr(child, 'objectValues'):
                walk(child)

    walk(site)
    return sorted(found)


def _due(settings, last_run):
    now = datetime.now()
    frequency = getattr(settings, 'scheduler_frequency', 'hour') or 'hour'
    if frequency == 'minute':
        return last_run is None or (now - last_run).total_seconds() >= 60
    if frequency == 'day':
        try:
            hour, minute = (int(part) for part in (settings.scheduler_time or '02:00').split(':', 1))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, TypeError):
            hour, minute = 2, 0
        return (now.hour, now.minute) >= (hour, minute) and (
            last_run is None or last_run.date() != now.date()
        )
    return last_run is None or (now - last_run).total_seconds() >= 3600


def _run():
    last_run = None
    while True:
        app = None
        try:
            app = open_app()
            site = app.unrestrictedTraverse(os.environ.get('SITE_ID', 'Plone1'))
            setSite(site)
            registry = getUtility(IRegistry)
            ensure_settings_registry(registry)
            settings = registry.forInterface(IAgoraSyncSettings)
            if getattr(settings, 'scheduler_enabled', False) and _due(settings, last_run):
                models = _models(site)
                for model in models:
                    result = AgoraSyncView(site, _Request({'model_name': model}))()
                    logger.info('Automatic Agora synchronization for %s: %s', model, result)
                transaction.commit()
                last_run = datetime.now()
        except Exception:
            logger.exception('Automatic Agora synchronization failed')
            transaction.abort()
        finally:
            if app is not None:
                try:
                    app._p_jar.close()
                except Exception:
                    pass
        time.sleep(60)


def start_scheduler(event):
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_run, name='agora-scheduler', daemon=True)
    thread.start()
