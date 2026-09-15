from __future__ import annotations

import re
from typing import Any

from trigrix_studio.project.models import EmailSettings


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailConfigurationError(ValueError):
    pass


def validate_email_settings(settings: EmailSettings, platform: str | None = None) -> list[str]:
    errors: list[str] = []
    if not settings.enabled:
        return errors
    if not EMAIL_RE.fullmatch(settings.sender_address):
        errors.append("Enter a valid sender address.")
    invalid = [address for address in settings.recipients if not EMAIL_RE.fullmatch(address)]
    if invalid:
        errors.append("Invalid recipient addresses: " + ", ".join(invalid))
    if settings.mode == "cloudflare_free":
        if platform == "docker":
            errors.append("Cloudflare Free Email binding is available only in a Cloudflare Worker.")
        if not settings.binding_name.isidentifier():
            errors.append("Email binding name must be a valid identifier.")
        unverified = sorted(set(settings.recipients) - set(settings.verified_recipients))
        if unverified:
            errors.append('Cloudflare Free allows only confirmed recipients:' + ", ".join(unverified))
    elif settings.mode == "smtp":
        if platform == "cloudflare":
            errors.append("SMTP is for Docker/VPS; use Cloudflare binding or Email API in Workers.")
        if not settings.smtp_host:
            errors.append("Enter an SMTP host.")
    elif not settings.api_url:
        errors.append("Enter an Email API endpoint.")
    return errors


def cloudflare_send_email_binding(settings: EmailSettings) -> dict[str, Any] | None:
    if not settings.enabled or settings.mode != "cloudflare_free":
        return None
    errors = validate_email_settings(settings, "cloudflare")
    if errors:
        raise EmailConfigurationError(" ".join(errors))
    binding: dict[str, Any] = {"name": settings.binding_name, "remote": True}
    if len(settings.verified_recipients) == 1:
        binding["destination_address"] = settings.verified_recipients[0]
    elif settings.verified_recipients:
        binding["allowed_destination_addresses"] = settings.verified_recipients
    if settings.sender_address:
        binding["allowed_sender_addresses"] = [settings.sender_address]
    return binding
