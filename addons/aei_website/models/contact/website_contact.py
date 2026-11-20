"""Public contact form validation and mail creation for /contactus."""
import re

from markupsafe import Markup, escape

from odoo import models

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
FIELD_MAX_LENGTHS = {
    "name": 120,
    "phone": 40,
    "email_from": 150,
    "company": 120,
    "subject": 180,
    "description": 4000,
}
DEFAULT_CONTACT_RECIPIENT = "ebendek@ribentek.com"
CONTACT_RECIPIENT_PARAM = "aei_website.contact_recipient"


class WebsiteContact(models.Model):
    """Validates untrusted /contactus submissions and queues a sanitized mail.mail record."""

    _inherit = "website"

    def submit_aei_contact_form(self, payload):
        """Validate the submitted contact fields and create a mail.mail record when valid.

        Returns a tuple ``(ok, cleaned_values)`` without leaking internal details.
        """
        self.ensure_one()
        cleaned = self._clean_contact_payload(payload or {})
        if (payload or {}).get("website_url"):
            # Honeypot triggered by automated bots: silently succeed without queuing mail.
            return True, cleaned
        if not self._is_valid_contact_payload(cleaned):
            return False, cleaned
        recipient = self._aei_contact_recipient()
        body_html = self._build_contact_mail_body(cleaned)
        self.env["mail.mail"].sudo().create(
            {
                "subject": f"[Contacto AEI] {cleaned['subject']}",
                "email_from": self.company_id.email_formatted or cleaned["email_from"],
                "reply_to": cleaned["email_from"],
                "email_to": recipient,
                "body_html": body_html,
            }
        )
        return True, cleaned

    def _aei_contact_recipient(self):
        """Return the address(es) that receive the inquiries.

        Read from the system parameter ``aei_website.contact_recipient`` (editable in
        Settings > Website). One address or several separated by commas; if the value is
        empty or any address is malformed it falls back to the commercial mailbox, so a
        typo can never make the inquiries vanish.
        """
        raw = self.env["ir.config_parameter"].sudo().get_param(CONTACT_RECIPIENT_PARAM) or ""
        addresses = [item.strip() for item in raw.split(",") if item.strip()]
        if addresses and all(EMAIL_PATTERN.fullmatch(item) for item in addresses):
            return ", ".join(addresses)
        return DEFAULT_CONTACT_RECIPIENT

    def _clean_contact_payload(self, payload):
        """Normalize whitespace and clamp candidate string inputs."""
        cleaned = {}
        for key in FIELD_MAX_LENGTHS:
            raw = payload.get(key, "")
            value = raw.strip() if isinstance(raw, str) else ""
            cleaned[key] = value
        return cleaned

    def _is_valid_contact_payload(self, cleaned):
        """Enforce required fields, allow-listed lengths, and basic email format."""
        for required_key in ("name", "email_from", "subject", "description"):
            if not cleaned.get(required_key):
                return False
        for key, max_len in FIELD_MAX_LENGTHS.items():
            if len(cleaned.get(key, "")) > max_len:
                return False
        if not EMAIL_PATTERN.fullmatch(cleaned["email_from"]):
            return False
        if "\r" in cleaned["email_from"] or "\n" in cleaned["email_from"]:
            return False
        return True

    def _build_contact_mail_body(self, cleaned):
        """Build an HTML-escaped mail body from validated visitor inputs."""
        return Markup(
            "<div>"
            "<p><strong>Nueva consulta desde el sitio web de AEI Software</strong></p>"
            "<ul>"
            "<li><strong>Nombre:</strong> {name}</li>"
            "<li><strong>Correo:</strong> {email}</li>"
            "<li><strong>Teléfono:</strong> {phone}</li>"
            "<li><strong>Empresa:</strong> {company}</li>"
            "<li><strong>Asunto:</strong> {subject}</li>"
            "</ul>"
            "<p><strong>Mensaje:</strong></p>"
            "<p>{description}</p>"
            "</div>"
        ).format(
            name=escape(cleaned["name"]),
            email=escape(cleaned["email_from"]),
            phone=escape(cleaned["phone"] or "—"),
            company=escape(cleaned["company"] or "—"),
            subject=escape(cleaned["subject"]),
            description=escape(cleaned["description"]).replace("\n", Markup("<br/>")),
        )

