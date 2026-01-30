import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Any, Dict
import logging
from jinja2 import Template

from app.config import get_settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.settings = get_settings()

    def send_email(
        self,
        email_to: str,
        subject: str,
        template_str: str,
        template_data: Dict[str, Any],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Versendet eine E-Mail via SMTP.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.settings.emails_from_name} <{self.settings.emails_from_email}>"
            msg["To"] = email_to
            
            if cc:
                msg["Cc"] = ", ".join(cc)
            
            # Render Body
            template = Template(template_str)
            html_content = template.render(**template_data)
            
            # Text fallback (simple strip tags could be better but basic text is ok)
            text_content = html_content.replace("<br>", "\n").replace("</p>", "\n\n")
            
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.debug:
                    server.set_debuglevel(1)
                
                # TLS/StartTLS logic
                if self.settings.smtp_port == 587:
                    server.starttls()
                
                if self.settings.smtp_user and self.settings.smtp_password:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email sent to {email_to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {email_to}: {e}")
            return False

# Singleton
email_service = EmailService()

PAYMENT_REMINDER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head></head>
<body>
    <p>Hallo {{ customer_name }},</p>
    
    <p>leider konnten wir für folgende Rechnung noch keinen Zahlungseingang feststellen:</p>
    
    <p>
        <strong>Rechnungsnummer:</strong> {{ invoice_number }}<br>
        <strong>Datum:</strong> {{ invoice_date }}<br>
        <strong>Fälligkeit:</strong> {{ due_date }}<br>
        <strong>Offener Betrag:</strong> {{ amount }} EUR
    </p>
    
    <p>Bitte überweisen Sie den Betrag von <strong>{{ amount }} EUR</strong> bis zum <strong>{{ new_deadline }}</strong> auf unser Konto.</p>
    
    <p>Falls sich Ihre Zahlung mit diesem Schreiben überschnitten hat, betrachten Sie es bitte als gegenstandslos.</p>
    
    <p>Mit freundlichen Grüßen,<br>
    Ihr Minga Greens Team</p>
</body>
</html>
"""
