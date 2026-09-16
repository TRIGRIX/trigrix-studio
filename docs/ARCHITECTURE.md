# Architecture

TRIGRIX Studio separates the editor and the created bot. GUI changes only `BotProject`. Validator checks graph, capacity matrix channels, links, integrations and stateless restrictions. The compiler assigns short runtime ID and creates a single canonical IR. Both generators receive only IR and Jinja2 templates.

```text
PySide6 GUI → BotProject → GraphValidator → IR → Cloudflare generator
                                            └→ Docker generator
```

```text
Official webhook → Channel adapter → Canonical event → Flow runtime → Structured lead
                                                              ├→ Admin notification
                                                              ├→ Cloudflare Email / API / SMTP
                                                              ├→ CRM adapter
                                                              └→ Firestore → XLSX / CSV
```

Namespaced user IDs as `channel:account_id:user_id`. Each delivery has an independent result; failure CRM or Email does not cancel an already accepted order. Dialogues are not transferred to the application repository.

The generated code does not import TRIGRIX Studio and continues to work after removal of the constructor.
