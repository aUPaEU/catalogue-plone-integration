from zope.interface import Interface
from zope.schema import Bool, Choice, Password, TextLine


class IAgoraSyncSettings(Interface):
    """Server-side settings for importing catalogue detail pages."""

    api_base_url = TextLine(
        title="Odoo catalogue API base URL",
        description="For example: https://odoo.example.org/catalogue-api/v2",
        required=False,
    )
    browser_base_url = TextLine(
        title="Odoo browser base URL",
        description="Public Odoo origin used in links shown to browsers; leave empty for local Docker (host.docker.internal becomes localhost).",
        required=False,
    )
    api_token = Password(
        title="Odoo catalogue API token",
        description="Stored in Plone and used only by the server-side synchronizer.",
        required=False,
    )
    scheduler_enabled = Bool(
        title="Enable automatic synchronization",
        description="Synchronize catalogue models found in Agora components automatically.",
        required=False,
        default=False,
    )
    scheduler_frequency = Choice(
        title="Synchronization frequency",
        description="How often automatic synchronization runs.",
        vocabulary="collective.agora.frequencies",
        required=False,
        default="hour",
    )
    scheduler_time = TextLine(
        title="Daily synchronization time",
        description="24-hour time (HH:MM), used when frequency is daily.",
        required=False,
        default="02:00",
    )


class IAgoraSyncedDocument(Interface):
    """Marker for catalogue detail pages managed by Agora synchronization."""
def ensure_settings_registry(registry):
    """Register settings for sites installed before this add-on version."""
    # RegistryEditForm calls forInterface(schema) without a custom prefix.
    # Registering with a prefix creates a different record namespace and makes
    # the control panel fail before it can render the form.
    registry.registerInterface(IAgoraSyncSettings)
