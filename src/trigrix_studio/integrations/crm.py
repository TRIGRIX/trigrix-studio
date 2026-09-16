from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trigrix_studio.project.models import CRMIntegration


@dataclass(frozen=True, slots=True)
class CRMProvider:
    title: str
    default_base_url: str
    create_path: str
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer "
    self_hosted: bool = False
    regional: bool = False


CRM_PROVIDERS: dict[str, CRMProvider] = {
    "hubspot": CRMProvider("HubSpot", "https://api.hubapi.com", "/crm/v3/objects/contacts"),
    "salesforce": CRMProvider("Salesforce", "https://your-instance.my.salesforce.com", "/services/data/v61.0/sobjects/Lead"),
    "dynamics365": CRMProvider("Microsoft Dynamics 365", "https://your-org.crm.dynamics.com", "/api/data/v9.2/leads"),
    "pipedrive": CRMProvider("Pipedrive", "https://api.pipedrive.com", "/v1/leads"),
    "zoho": CRMProvider("Zoho CRM", "https://www.zohoapis.com", "/crm/v8/Leads", auth_prefix="Zoho-oauthtoken "),
    "freshsales": CRMProvider("Freshsales", "https://your-domain.myfreshworks.com", "/crm/sales/api/contacts", "Authorization", "Token token="),
    "odoo": CRMProvider("Odoo", "https://your-odoo.example", "/jsonrpc", self_hosted=True),
    "espocrm": CRMProvider("EspoCRM", "https://your-espo.example", "/api/v1/Lead", "X-Api-Key", "", True),
    "suitecrm": CRMProvider("SuiteCRM", "https://your-suite.example", "/Api/V8/module/Leads", self_hosted=True),
    "frappe": CRMProvider("Frappe CRM", "https://your-frappe.example", "/api/resource/CRM Lead", "Authorization", "token ", True),
    "bitrix24": CRMProvider("Bitrix24", "https://your-portal.bitrix24.com", "/rest/crm.lead.add.json", regional=True),
    "amocrm": CRMProvider("amoCRM", "https://your-domain.amocrm.ru", "/api/v4/leads", regional=True),
    "retailcrm": CRMProvider("RetailCRM", "https://your-domain.retailcrm.ru", "/api/v5/orders/create", regional=True),
    "planfix": CRMProvider("Planfix", "https://your-account.planfix.com", "/rest/task/", regional=True),
    "megaplan": CRMProvider('Megaplane', "https://your-domain.megaplan.ru", "/api/v3/deals", regional=True),
    "yclients": CRMProvider("YCLIENTS", "https://api.yclients.com", "/api/v1/records", regional=True),
    "onec": CRMProvider('1C:CRM', "https://your-1c.example", "/odata/standard.odata/Lead", regional=True),
    "webhook": CRMProvider("REST / Webhook", "", ""),
}


def build_crm_request(integration: CRMIntegration, lead: dict[str, Any], token: str) -> dict[str, Any]:
    provider = CRM_PROVIDERS[integration.provider]
    base = (integration.base_url or provider.default_base_url).rstrip("/")
    path = str(integration.settings.get("create_path", provider.create_path))
    mapped: dict[str, Any] = {}
    mapping = integration.field_mapping or {
        "name": "name", "email": "email", "phone": "phone", "status": "status",
        "channel_user_id": "channel_user_id", "lead_id": "external_id",
    }
    for source, target in mapping.items():
        value: Any = lead
        for part in source.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, ""):
            mapped[target] = value
    if integration.pipeline:
        mapped["pipeline"] = integration.pipeline
    if integration.status:
        mapped["status"] = integration.status
    if integration.owner:
        mapped["owner"] = integration.owner
    headers = {"Content-Type": "application/json", provider.auth_header: provider.auth_prefix + token}
    if integration.provider == "hubspot": body: dict[str, Any] = {"properties": mapped}
    elif integration.provider == "zoho": body = {"data": [mapped]}
    elif integration.provider == "freshsales": body = {"contact": mapped}
    elif integration.provider == "frappe": body = {"data": mapped}
    elif integration.provider == "suitecrm": body = {"data": {"type": "Leads", "attributes": mapped}}
    elif integration.provider == "odoo":
        body = {"jsonrpc": "2.0", "method": "call", "params": {"service": "object", "method": "execute_kw", "args": [integration.settings.get("database", ""), integration.settings.get("uid", 0), token, "crm.lead", "create", [mapped]]}, "id": lead.get("lead_id")}
    else: body = mapped
    return {"method": "POST", "url": base + path, "headers": headers, "json": body, "timeout": 20}
