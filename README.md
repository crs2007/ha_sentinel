# HA Sentinel

**HA Sentinel** is a Home Assistant custom integration that safely auto-updates your installation — Home Assistant Core/OS/Supervisor, Add-ons, and HACS integrations — using a configurable policy engine. It filters beta releases, enforces stability delays before installing anything new, and detects breaking changes automatically.

> **Safe by design:** HA Sentinel ships in **dry-run mode by default**. It will observe, score, and notify you about available updates without installing anything until you explicitly opt in per provider.

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![CI][ci-badge]][ci-url]
[![License: MIT][license-badge]][license-url]

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://hacs.xyz
[release-badge]: https://img.shields.io/github/v/release/crs2007/ha_sentinel
[release-url]: https://github.com/crs2007/ha_sentinel/releases
[ci-badge]: https://github.com/crs2007/ha_sentinel/actions/workflows/tests.yml/badge.svg
[ci-url]: https://github.com/crs2007/ha_sentinel/actions/workflows/tests.yml
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[license-url]: https://github.com/crs2007/ha_sentinel/blob/main/LICENSE

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Via HACS (Recommended)](#via-hacs-recommended)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
  - [Initial Setup](#initial-setup)
  - [All Options](#all-options)
  - [Allowlist & Blocklist](#allowlist--blocklist)
- [Services](#services)
- [Notifications](#notifications)
- [Update Pipeline](#update-pipeline)
- [Breaking-Change Detection](#breaking-change-detection)
- [Providers](#providers)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Running Tests](#running-tests)
  - [Architecture Notes](#architecture-notes)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Three update providers** — Home Assistant Core/OS/Supervisor, Supervisor Add-ons, and HACS integrations/frontend cards
- **Dry-run mode by default** — observe and notify without installing anything; opt in per provider when you're ready
- **Stability delay** — waits a configurable number of days after a new version first appears before approving it (default: 7 days); resets automatically if the version changes again
- **Beta filtering** — silently skips pre-release and beta versions (enabled by default)
- **Breaking-change detection** — scores release notes using keyword weights and version-jump analysis; pauses updates that exceed your confidence threshold
- **Allowlist / Blocklist** — pin exactly which slugs may or may not auto-update, independent of all other rules
- **Persistent notification summary** — one clean HA notification replaced each cycle; no notification spam
- **GUI configuration** — all options are set through the standard HA Options Flow UI; no YAML needed
- **Services** — trigger an immediate check or force-install a specific slug from automations or the Developer Tools
- **HACS-compatible** — distributed via HACS; validates with the official `hacs` and `hassfest` CI actions

---

## How It Works

Every 6 hours (configurable), HA Sentinel runs a five-step pipeline:

1. **Fetch** — each enabled provider queries available updates concurrently
2. **Track** — every candidate version is recorded with a `first_seen` timestamp; the clock resets if the version changes
3. **Decide** — the policy engine evaluates each candidate in order: beta filter → stability delay → breaking-change score → dry-run / provider enabled → blocklist → allowlist → **INSTALL**
4. **Execute** — approved `INSTALL` decisions are applied sequentially per provider
5. **Notify** — a single persistent notification summarising all decisions replaces the previous one

The full decision order is:

| Priority | Condition | Action |
|---|---|---|
| 1 | Is beta AND `ignore_beta` is on | `SKIP` |
| 2 | Stability window not yet met | `DELAY` |
| 3 | Breaking score ≥ threshold AND `pause_on_breaking` is on | `SKIP` |
| 4 | `dry_run` is on OR provider not in `enabled_providers` | `NOTIFY_ONLY` |
| 5 | Slug is on `blocklist` | `SKIP` |
| 6 | `allowlist` is non-empty AND slug is not on it | `SKIP` |
| 7 | All checks passed | `INSTALL` |

---

## Requirements

- Home Assistant **2023.4** or newer
- [HACS](https://hacs.xyz) installed (only required for the HACS provider; the integration itself installs without it)
- A **supervised** HA installation (Home Assistant OS or Supervised) for Core and Add-on providers; those providers gracefully disable themselves on container/core installs

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Click **Integrations** → **⋮ menu** → **Custom repositories**.
3. Add `https://github.com/crs2007/ha_sentinel` with category **Integration**.
4. Search for **HA Sentinel** and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **HA Sentinel**.

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/crs2007/ha_sentinel/releases).
2. Copy the `custom_components/ha_sentinel` folder into your HA `config/custom_components/` directory.
3. Restart Home Assistant.
4. Add the integration via **Settings → Devices & Services**.

---

## Configuration

### Initial Setup

The integration is set up through a single confirmation step. No options are required at install time — the integration starts in safe dry-run mode automatically.

After setup, open **Settings → Devices & Services → HA Sentinel → Configure** to adjust any option.

### All Options

| Option | Default | Description |
|---|---|---|
| `dry_run` | `true` | When enabled, no updates are installed — decisions are logged and notified only. Set to `false` to allow real installs. |
| `enabled_providers` | `["core", "addon", "hacs"]` | Which provider(s) are allowed to perform real installs when dry-run is off. |
| `ignore_beta` | `true` | Skip any candidate marked as a pre-release or beta version. |
| `pause_on_breaking` | `true` | Hold updates whose release notes score above the breaking threshold. |
| `breaking_threshold` | `0.5` | Confidence score (0.0–1.0) above which an update is considered risky. Lower = more cautious. |
| `stability_delay_days` | `7` | Days a version must be visible before it qualifies for installation. Range: 0–90. |
| `check_interval_hours` | `6` | How often the pipeline runs. Range: 1–168. |
| `allowlist` | `[]` | If non-empty, only slugs on this list can be auto-installed. Leave empty to allow all. |
| `blocklist` | `[]` | Slugs that are never auto-installed, regardless of other settings. |

### Allowlist & Blocklist

Both lists accept **slug strings** — the internal identifier for a component. Examples:

- Home Assistant Core slug: `homeassistant`
- A HACS integration slug: matches the GitHub repository name used by HACS (e.g., `hass-bha-icons`)
- A Supervisor add-on slug: the add-on's slug as shown in the Supervisor panel (e.g., `core_mosquitto`)

**Allowlist behaviour:** if any entries are present, _only_ those slugs can progress to `INSTALL`. All others receive `SKIP`.

**Blocklist behaviour:** listed slugs always receive `SKIP`, even if they appear on the allowlist.

---

## Services

HA Sentinel registers two services under the `ha_sentinel` domain, available in Developer Tools → Services or callable from automations.

### `ha_sentinel.check_now`

Triggers an immediate fetch-and-decide cycle without installing anything. Useful for checking what is pending after a HA update or before a planned change window.

```yaml
service: ha_sentinel.check_now
```

### `ha_sentinel.install_now`

Force-installs a single update by slug, bypassing `dry_run` and all policy rules. Use with care.

```yaml
service: ha_sentinel.install_now
data:
  slug: "core_mosquitto"
```

---

## Notifications

After each cycle, HA Sentinel creates (or replaces) a single **persistent notification** with ID `ha_sentinel_summary`. The notification lists every candidate and its decision:

- **INSTALL** — update was applied
- **NOTIFY_ONLY** — dry-run mode; update is ready but was not installed
- **DELAY** — still within the stability window; shows time remaining
- **SKIP** — filtered by beta, breaking-change detection, blocklist, or allowlist

Dismiss the notification at any time — it will be regenerated on the next cycle.

---

## Update Pipeline

```
Coordinator (every N hours)
  └─ UpdateManager.run_cycle()
       ├─ asyncio.gather → [CoreProvider, AddonProvider, HacsProvider].fetch_candidates()
       ├─ VersionTracker.update(candidate)   ← first_seen timer-reset logic
       ├─ policy_engine.decide(candidate)    ← pure function, no side effects
       ├─ provider.install(candidate)        ← only for INSTALL decisions, sequential
       └─ notifier.notify_summary()          ← replaces prior notification
```

The version tracker's timer-reset algorithm is the key safety guarantee:

- **New version seen for the first time** → `first_seen` is set to now; the stability clock starts
- **Same version on subsequent cycles** → `first_seen` is unchanged; clock keeps running
- **Version changes again** (e.g., 2025.1 → 2025.2 mid-window) → `first_seen` resets; clock restarts
- **Version rolls back** → record is deleted; treated as a brand-new candidate next cycle

---

## Breaking-Change Detection

Release notes are scored using keyword matching and version-jump analysis. Scores are additive and clamped to `[0.0, 1.0]`.

**Keyword weights:**

| Phrase | Weight |
|---|---|
| `breaking change` / `breaking:` | +0.60 |
| `migration required` | +0.50 |
| `incompatible` | +0.40 |
| `removed` / `you must` | +0.20 |
| `deprecated` / `no longer` | +0.15 |

**Version-jump weights:**

| Jump type | Weight |
|---|---|
| SemVer major bump | +0.40 |
| SemVer minor bump | +0.10 |
| CalVer year change | +0.30 |

If the total score meets or exceeds `breaking_threshold` (default `0.5`) and `pause_on_breaking` is on, the update is held with a `SKIP` decision and the score is shown in the notification.

---

## Providers

### Core (`core`)

Queries `http://supervisor/core/info` and `http://supervisor/os/info` via the Supervisor REST API. Requires `SUPERVISOR_TOKEN` environment variable (present automatically on HA OS / Supervised). Disabled silently on container/core installs.

### Add-ons (`addon`)

Queries `http://supervisor/addons` for all installed add-ons and their update status. Same Supervisor requirement as the Core provider.

### HACS (`hacs`)

Reads pending updates from `hass.data["hacs"]` — the in-memory HACS state already managed by the HACS integration. Never imports HACS modules directly; gracefully marks itself unavailable when HACS is not installed.

---

## Development

### Project Structure

```
custom_components/ha_sentinel/
  __init__.py           # Entry setup, service registration
  manifest.json         # Integration metadata
  const.py              # DOMAIN, defaults, config keys, keyword weights
  models.py             # UpdateCandidate, Decision, SentinelConfig dataclasses
  coordinator.py        # DataUpdateCoordinator wrapper
  update_manager.py     # Fetch → track → decide → install → notify pipeline
  version_tracker.py    # Storage-backed stability timer with reset algorithm
  policy_engine.py      # Pure decision function
  breaking_changes.py   # Keyword + version-jump confidence scorer
  config_flow.py        # ConfigFlow (confirm) + OptionsFlow (all settings)
  notifier.py           # Persistent notification builder
  providers/
    base.py             # Abstract UpdateProvider interface
    core.py             # HA Core + OS provider
    addon.py            # Supervisor add-on provider
    hacs.py             # HACS integration/frontend provider
tests/
  conftest.py
  test_version_tracker.py
  test_breaking_changes.py
  test_policy_engine.py
  test_providers_hacs.py
  fixtures/             # JSON fixtures for provider responses
```

### Running Tests

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run the full test suite
pytest tests/ -v

# Run a single test file
pytest tests/test_version_tracker.py -v

# Run a single test by name
pytest tests/test_policy_engine.py::test_beta_filtered -v
```

CI runs automatically on every push and pull request to `main`:

- **`hassfest`** — validates `manifest.json` and integration structure against HA standards
- **`hacs`** — validates `hacs.json` and repository layout
- **`tests`** — runs `pytest tests/ -v`

### Architecture Notes

- `policy_engine.decide()` is a **pure function** — no I/O, no side effects. Pass a candidate, config, and tracker; get a Decision back. Test it exhaustively.
- `version_tracker.py` is load-bearing. The timer-reset invariant ("same version → keep `first_seen` unchanged") must never be broken. Tests for rollback, new-version reset, and missing-record cases are critical.
- `breaking_changes.score()` operates only on the release notes string. It has no external dependencies and is independently testable.
- Providers **must not** raise exceptions during `fetch_candidates()` — the manager catches exceptions from `asyncio.gather` and logs a warning, keeping the cycle alive for other providers.

---

## Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository and create a feature branch from `main`.
2. **Install** test dependencies: `pip install -r requirements_test.txt`
3. **Write tests first** — the project follows TDD; untested changes will not be merged.
4. **Run the full test suite** and make sure everything passes before opening a PR.
5. **Keep PRs focused** — one logical change per pull request.
6. **Open an issue first** for significant features or behaviour changes, so the approach can be discussed before implementation.

Please report bugs and feature requests in the [GitHub Issues tracker](https://github.com/crs2007/ha_sentinel/issues).

### Out of Scope for v1

The following are intentionally deferred: mobile push notifications, HA Repairs/issue registry integration, canary/staged rollout mode, automatic rollback, post-update health checks, and time-of-day update scheduling.

---

## License

Released under the [MIT License](LICENSE). © 2026 [crs2007](https://github.com/crs2007).
