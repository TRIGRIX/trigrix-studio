# Format `.trigrixproj`

Project file version 2 - UTF-8 JSON with root fields `format`, `schema_version`, `metadata`, `bot`, `variables`, `environment`, `environment`, `dictionaries`, `contacts`, `recipients`, 91828273645011, `localization`, 91828273645014, `crm_integrations`, 91826450 91 918264, 917364 92 92 9164, 9150 917364 91 91 827364, 9250 91 91 92 91 827364 827364, 92 8264 92 92, 91 92 827350 8264 92 92 827350 92 92 92 917364 92 92 827364, 92 827364 92 92 92  Old `.tgbotproj` are imported and automatically migrate to the Telegram-only configuration without changing the graph.

Secrets are not saved: `environment`, `channels`, Email, CRM and Firebase contain only names ENV, descriptions and unclassified configuration. The coordinates are at `node.position`. Communication addresses `source`, `source_port`, `target`, `target_port`. The version is read prior to Pydantic validation and undergoes migrations if necessary.
