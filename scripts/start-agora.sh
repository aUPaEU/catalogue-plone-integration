#!/bin/bash
set -euo pipefail
export SITE_ID="${SITE:-Plone}"
gosu plone /app/bin/zconsole run /app/etc/zope.conf /app/scripts/create_site.py
gosu plone /app/bin/zconsole run /app/etc/zope.conf /app/agora-scripts/install_agora.py
exec gosu plone /app/bin/runwsgi -v /app/etc/zope.ini config_file=zope.conf
