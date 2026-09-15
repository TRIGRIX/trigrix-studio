"""Multichannel lead, notification, storage and CRM integration primitives."""

from .channels import CHANNELS, ChannelCapability, normalize_event
from .crm import CRM_PROVIDERS, CRMProvider, build_crm_request
from .email import EmailConfigurationError, cloudflare_send_email_binding, validate_email_settings
from .exports import export_leads_csv, export_leads_xlsx
from .models import CanonicalEvent, DeliveryResult, Lead
from .telegram_import import extract_telegram_export_leads

__all__ = [
    "CHANNELS", "CRM_PROVIDERS", "CanonicalEvent", "ChannelCapability",
    "CRMProvider", "DeliveryResult", "EmailConfigurationError", "Lead",
    "build_crm_request", "cloudflare_send_email_binding", "export_leads_csv",
    "export_leads_xlsx", "extract_telegram_export_leads", "normalize_event", "validate_email_settings",
]
