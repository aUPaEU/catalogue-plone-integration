"""Install once on the configured site, before the server opens the database."""
import os
import transaction
from AccessControl.SecurityManagement import newSecurityManager
from Testing.makerequest import makerequest
from zope.component.hooks import setSite

app = makerequest(globals()["app"])
admin = app.acl_users.getUserById("admin")
newSecurityManager(None, admin.__of__(app.acl_users))
site = app[os.environ.get("SITE", "Plone")]
setSite(site)
profile = "collective.agora:default"
if site.portal_setup.getLastVersionForProfile(profile) != ("1021",):
    site.portal_setup.runAllImportStepsFromProfile("profile-" + profile)
    transaction.commit()
    print("Installed Agora TinyMCE templates on", site.id)
else:
    print("Agora TinyMCE templates already installed on", site.id)
