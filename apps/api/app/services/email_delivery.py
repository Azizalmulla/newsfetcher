from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.core.config import Settings, get_settings


def deliver_report_email(
    *,
    recipients: list[str],
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
    settings: Settings | None = None,
) -> dict[str, object]:
    cfg = settings or get_settings()
    if not recipients:
        raise ValueError("At least one recipient is required")

    if cfg.email_backend == "console":
        return {
            "backend": "console",
            "recipients": recipients,
            "subject": subject,
            "pdf_bytes": len(pdf_bytes),
            "status": "sent",
        }

    if cfg.email_backend == "file":
        out_dir = Path(cfg.email_file_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = subject.replace("/", "_")[:80]
        msg_path = out_dir / f"{safe}.eml"
        message = _build_message(
            cfg=cfg,
            recipients=recipients,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
        msg_path.write_bytes(message.as_bytes())
        pdf_path = out_dir / pdf_filename
        pdf_path.write_bytes(pdf_bytes)
        return {
            "backend": "file",
            "recipients": recipients,
            "path": str(msg_path),
            "pdf_path": str(pdf_path),
            "status": "sent",
        }

    if cfg.email_backend == "smtp":
        if not cfg.smtp_host:
            raise ValueError("SMTP_HOST is required when EMAIL_BACKEND=smtp")
        message = _build_message(
            cfg=cfg,
            recipients=recipients,
            subject=subject,
            body=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=20) as smtp:
            if cfg.smtp_use_tls:
                smtp.starttls()
            if cfg.smtp_user:
                smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(message)
        return {"backend": "smtp", "recipients": recipients, "status": "sent"}

    raise ValueError(f"Unsupported email backend: {cfg.email_backend}")


def _build_message(
    *,
    cfg: Settings,
    recipients: list[str],
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = cfg.smtp_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_filename,
    )
    return message
