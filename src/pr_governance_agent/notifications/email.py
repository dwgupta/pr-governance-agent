import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from pr_governance_agent.config import ROOT_DIR, get_settings


def send_notification(
    subject: str,
    body: str,
    *,
    passed: bool,
) -> bool:
    settings = get_settings()
    log_path = ROOT_DIR / "data" / "notification.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).isoformat()
    status = "PASS" if passed else "FAIL"
    entry = f"\n--- {stamp} [{status}] {subject} ---\n{body}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)

    if not settings.smtp_host or not settings.notify_to:
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.notify_from or settings.smtp_user
    msg["To"] = settings.notify_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except OSError as exc:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"SMTP error: {exc}\n")
        return False
    return True
