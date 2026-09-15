# TRIGRIX Studio

TRIGRIX Studio is an open-source visual builder for conversational bots, lead forms, and multichannel workflows. Design a scenario on a node canvas, configure integrations in one place, validate it, test it locally, and export a standalone runtime for Cloudflare Workers or Docker.

![TRIGRIX Studio branding](resources/branding/trigrix-logo-1200.png)

## Why TRIGRIX Studio?

- **Visual, node-based editor** — drag blocks from the library to the canvas and connect branches without writing boilerplate code.
- **Real answer choices** — add buttons, menus, directory-backed options, conditions, variables, and forms directly in the block inspector. All choices remain visible in the flow.
- **One canonical workflow** — the editor compiles a project into a channel-neutral intermediate representation (IR), then generates the selected targets from the same model.
- **Multichannel architecture** — configure Telegram, WhatsApp Business, Instagram Messaging, Facebook Messenger, and extensible channel adapters from one project. Capability validation warns about channel-specific limitations before export.
- **Structured lead capture** — collect names, phone numbers, email addresses, custom fields, files, and answers, then build an administrator-facing lead card.
- **Delivery integrations** — route structured leads to Firebase Firestore, email, CRM systems, and Telegram administrators. Delivery branches are independent, so one failed integration does not hide a received lead.
- **Cloudflare Free email path** — generate a Worker using the `send_email` binding for notifications to confirmed Email Routing destinations, without silently enabling a paid Workers feature.
- **CRM connectivity** — built-in contracts for HubSpot, Salesforce, Microsoft Dynamics 365, Pipedrive, Zoho CRM, Freshsales, Odoo, EspoCRM, SuiteCRM, Frappe CRM, Bitrix24, amoCRM, RetailCRM, Planfix, Megaplan, YCLIENTS, 1C:CRM, and a generic REST/Webhook connector.
- **Lead export** — export structured submissions to XLSX/CSV from the administrator flow. The export contains lead data and answers, not a full chat transcript.
- **Secure project files** — projects are UTF-8 JSON files. Secrets are kept in the current session and exported as environment-variable names, never as tokens inside project files or ZIP archives.
- **Code mode on demand** — the generated preview is hidden by default. Enable Code Mode to inspect and edit the generated Python, JSON/JSONC, TOML, and YAML views with line numbers, syntax highlighting, and validation.
- **Built-in simulator and validator** — test a scenario before deployment and get graph, integration, capability, and configuration diagnostics.
- **Knowledge Base** — a searchable, glossary-style in-app wiki explains every tab, field, credential, webhook, channel, and integration.
- **74+ industry templates** — ready-to-edit flows for web studios, video production, motion design, branding, marketing, e-commerce, real estate, education, events, hospitality, B2B/IT, HR, communities, and more.
- **Internationalization** — the desktop interface and bot text resources support `en-US`, `de-DE`, `fr-FR`, `es-ES`, `pt-BR`, `it-IT`, `nl-NL`, `pl-PL`, `tr-TR`, and `ru-RU`.

## Generated runtimes

Both generators consume the same compiled workflow:

- **Cloudflare Worker** — one standalone `worker.js` for a stateless webhook deployment without KV, D1, R2, Durable Objects, Node.js, or Wrangler. A localized deployment guide is embedded at the beginning of the file.
- **Docker** — Python 3.13 application using aiogram 3 and long polling, suitable for a VPS or container platform.

Short-lived dialog state is transported in a signed HMAC Context Capsule. The exported bot is independent of TRIGRIX Studio and can be edited after export.

## Interface

The main window combines a block library, a visual graph canvas, a selected-node inspector, validation output, logs, project settings, channels, integrations, and export controls. The Knowledge Base opens as a separate window and can be searched by topic.

![TRIGRIX Studio icon](resources/branding/trigrix-icon-256.png)

## Quick start for development

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python run_trigrix_studio.py
```

On Linux or macOS, activate `.venv/bin/activate`; the remaining commands are the same.

## Windows build

Run:

```powershell
build_windows.bat
```

The portable application is generated in `dist/TRIGRIX Studio/`. Python is not required on the target computer. The TRIGRIX icon is embedded in the executable and bundled with the application resources.

## macOS Apple Silicon build

TRIGRIX Studio can be built as a native `arm64` application for Apple Silicon Macs (M1 and newer). On an Apple Silicon Mac, run:

```bash
bash build_macos_arm64.sh
```

The script verifies the native architecture, creates the macOS icon, runs the test suite, builds `TRIGRIX Studio.app`, applies an ad-hoc signature, and produces:

- `dist/TRIGRIX-Studio-macOS-arm64.zip`
- `dist/TRIGRIX-Studio-macOS-arm64.dmg`

The same build is available from the **Build macOS Apple Silicon** GitHub Actions workflow. Run it manually from the Actions tab or push the version tag `v1.0.0`, then download the `TRIGRIX-Studio-macOS-arm64` artifact.

The public build is ad-hoc signed. A Developer ID signature and Apple notarization require an Apple Developer account and are intentionally kept separate from the reproducible open-source build.

## Templates

The [template catalog](resources/templates/) contains more than 70 editable scenarios. A neutral [web-studio template](resources/templates/web-studio.trigrixproj) is included as both a practical starting point and a representative project fixture.

## Project structure

```text
src/trigrix_studio/
├── compiler/       # Project → canonical IR
├── generators/     # Cloudflare and Docker generators
├── gui/            # PySide6 desktop interface
├── integrations/   # Channels, email, CRM, Firebase, exports
├── nodes/          # Block registry and settings models
├── project/        # Pydantic models, IO, migrations
├── runtime/        # Signed stateless context capsule
├── simulator/      # Local scenario engine
├── templates/      # Built-in template factory
└── validator/      # Graph and integration validation
```

## Extending the block library

1. Add a Pydantic settings model in `src/trigrix_studio/nodes/settings.py`.
2. Register a `NodeDefinition` in `src/trigrix_studio/nodes/registry.py`.
3. Add compiler and simulator behavior.
4. Add the generated-runtime implementation for both targets.
5. Add tests for validation, simulation, and generated output.

See the [architecture guide](docs/ARCHITECTURE.md), [project format](docs/PROJECT_FORMAT.md), [node development guide](docs/NODE_DEVELOPMENT.md), [Cloudflare generator guide](docs/CLOUDFLARE_GENERATOR.md), [Docker generator guide](docs/DOCKER_GENERATOR.md), and [testing guide](docs/TESTING.md).

## Security and privacy

TRIGRIX Studio works locally. Project files contain workflow structure and configuration metadata, not bot tokens or API credentials. Runtime values entered for testing remain in memory for the current session. Review [docs/PRIVACY.md](docs/PRIVACY.md) before publishing a generated bot.

## Open source

Copyright © 2026 TRIGRIX Studio. Developed by Pavel Yemelianov. Free software released under the [GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`). [Website](https://trigrix.github.io/) · [GitHub](https://github.com/TRIGRIX/trigrix-studio) · [Issues](https://github.com/TRIGRIX/trigrix-studio/issues) · [Support](https://trigrix.github.io/donate.html).

## Tests

```powershell
pytest
```
