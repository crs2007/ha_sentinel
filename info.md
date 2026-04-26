# HA Sentinel

Safe auto-update integration for Home Assistant. Applies updates from Core/OS/Supervisor, Add-ons, and HACS according to a configurable policy engine:

- **Stability delay** — wait N days after a version first appears before installing
- **Beta filtering** — skip pre-releases by default
- **Breaking-change protection** — confidence-scored release-note analysis
- **Aggregated notifications** — one summary per update cycle, not per component
- **Dry-run by default** — notifies without installing until you opt in

## Setup

1. Install via HACS → Integrations → search "HA Sentinel"
2. Add integration: Settings → Devices & Services → Add Integration → HA Sentinel
3. Review defaults in Options (all safe; dry-run is on by default)
4. Call service `ha_sentinel.check_now` to trigger an immediate policy run
