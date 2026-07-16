import os
from typing import Optional
import resend
from app.config import settings
from app.email.templates import EmailTemplates

class EmailService:
    def __init__(self):
        self.client = None
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY
            self.client = True
            print("✅ Resend email service initialized")
        else:
            print("⚠️ RESEND_API_KEY not set. Email notifications disabled.")

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send a generic email"""
        if not self.client:
            return False
        
        try:
            params = {
                "from": settings.EMAIL_FROM or "FrankTech <alerts@franktechspace.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            response = resend.Emails.send(params)
            print(f"✅ Email sent to {to_email} (ID: {response.get('id')})")
            return True
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False

    async def send_error_alert(
        self,
        to_email: str,
        error: dict,
        analysis: dict,
        project_name: str = "Default Project",
        dashboard_url: str = "https://monitor.franktechspace.dev",
    ) -> bool:
        """Send an email alert for a critical error"""
        if not self.client:
            return False
        
        severity = error.get('severity', 'error').lower()
        severity_class = {
            'critical': 'severity-critical',
            'error': 'severity-error',
            'warning': 'severity-warning',
        }.get(severity, 'severity-error')
        
        from datetime import datetime
        time_str = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
        
        stack_trace = error.get('stack_trace', 'No stack trace available')
        if stack_trace and len(stack_trace) > 500:
            stack_trace = stack_trace[:500] + "...\n[truncated]"
        
        fix_content = ""
        if analysis and analysis.get('suggested_fix'):
            fix_content = f"""
            <div class="fix-box">
                <strong style="display: block; margin-bottom: 8px; color: #0f172a;">🤖 AI Suggested Fix</strong>
                <p style="margin: 4px 0 8px 0; color: #475569; font-size: 14px;">{analysis.get('root_cause', 'No root cause provided')}</p>
                <code>{analysis.get('suggested_fix', 'No fix provided')}</code>
                <div style="margin-top: 8px; font-size: 13px; color: #059669;">
                    Confidence: {int(analysis.get('confidence', 0) * 100)}%
                </div>
            </div>
            """
        
        html_content = EmailTemplates.ERROR_ALERT.substitute(
            error_type=error.get('type', 'Error'),
            error_message=error.get('message', 'Unknown error'),
            severity=severity.upper(),
            severity_class=severity_class,
            error_id=error.get('id', 'N/A'),
            project_name=project_name,
            time=time_str,
            stack_trace=stack_trace,
            fix_content=fix_content,
            dashboard_url=dashboard_url,
        )
        
        try:
            params = {
                "from": settings.EMAIL_FROM or "FrankTech <alerts@franktechspace.dev>",
                "to": [to_email],
                "subject": f"🚨 FrankTech Alert: {error.get('type', 'Error')} - {error.get('message', '')[:50]}",
                "html": html_content,
            }
            response = resend.Emails.send(params)
            print(f"✅ Email sent to {to_email} (ID: {response.get('id')})")
            return True
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False

    async def send_test_email(self, to_email: str) -> bool:
        """Send a test email"""
        if not self.client:
            return False
        
        try:
            params = {
                "from": settings.EMAIL_FROM or "FrankTech <alerts@franktechspace.dev>",
                "to": [to_email],
                "subject": "FrankTech - Email Test",
                "html": EmailTemplates.TEST_EMAIL.substitute(),
            }
            response = resend.Emails.send(params)
            print(f"✅ Test email sent to {to_email} (ID: {response.get('id')})")
            return True
        except Exception as e:
            print(f"❌ Failed to send test email: {e}")
            return False

email_service = EmailService()