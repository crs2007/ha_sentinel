"""Constants for HA Sentinel."""

DOMAIN = "ha_sentinel"
STORAGE_KEY = "ha_sentinel.version_history"
STORAGE_VERSION = 1

CONF_DRY_RUN = "dry_run"
CONF_ENABLED_PROVIDERS = "enabled_providers"
CONF_IGNORE_BETA = "ignore_beta"
CONF_PAUSE_ON_BREAKING = "pause_on_breaking"
CONF_BREAKING_THRESHOLD = "breaking_threshold"
CONF_STABILITY_DELAY_DAYS = "stability_delay_days"
CONF_CHECK_INTERVAL_HOURS = "check_interval_hours"
CONF_ALLOWLIST = "allowlist"
CONF_BLOCKLIST = "blocklist"
CONF_BACKUP_BEFORE_UPGRADE = "backup_before_upgrade"

PROVIDER_CORE = "core"
PROVIDER_ADDON = "addon"
PROVIDER_HACS = "hacs"
ALL_PROVIDERS = [PROVIDER_CORE, PROVIDER_ADDON, PROVIDER_HACS]

DEFAULT_DRY_RUN = True
DEFAULT_ENABLED_PROVIDERS = ALL_PROVIDERS
DEFAULT_IGNORE_BETA = True
DEFAULT_PAUSE_ON_BREAKING = True
DEFAULT_BREAKING_THRESHOLD = 0.5
DEFAULT_STABILITY_DELAY_DAYS = 7
DEFAULT_CHECK_INTERVAL_HOURS = 6
DEFAULT_ALLOWLIST: list[str] = []
DEFAULT_BLOCKLIST: list[str] = []
DEFAULT_BACKUP_BEFORE_UPGRADE = True

BREAKING_KEYWORDS: dict[str, float] = {
    "breaking change": 0.6,
    "breaking:": 0.6,
    "migration required": 0.5,
    "incompatible": 0.4,
    "removed": 0.2,
    "you must": 0.2,
    "deprecated": 0.15,
    "no longer": 0.15,
}

SERVICE_CHECK_NOW = "check_now"
SERVICE_INSTALL_NOW = "install_now"
SERVICE_DISMISS = "dismiss"

NOTIFICATION_ID = "ha_sentinel_summary"
