from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/api/v1/legal", tags=["Legal"])

@router.get("/terms")
async def get_terms():
    return {
        "version": "1.0",
        "effective_date": "2026-07-21",
        "content": {
            "title": "Terms of Service",
            "sections": [
                {
                    "heading": "1. Acceptance of Terms",
                    "text": "By accessing or using FrankTech Intelligence, you agree to be bound by these Terms of Service."
                },
                {
                    "heading": "2. Use of Service",
                    "text": "You must provide accurate information when creating an account. You may not misuse the service (e.g., attempting unauthorized access, distributing malware). FrankTech Intelligence is provided 'as-is' without guarantees of uninterrupted availability."
                },
                {
                    "heading": "3. Intellectual Property",
                    "text": "The FrankTech SDK, backend, and branding are owned by FrankTech. You may not copy, modify, or redistribute without permission."
                },
                {
                    "heading": "4. Account Suspension",
                    "text": "We reserve the right to suspend or terminate accounts that violate these terms."
                },
                {
                    "heading": "5. Limitation of Liability",
                    "text": "FrankTech Intelligence is not liable for damages resulting from use of the service."
                }
            ]
        }
    }

@router.get("/privacy")
async def get_privacy():
    return {
        "version": "1.0",
        "effective_date": "2026-07-21",
        "content": {
            "title": "Privacy Policy",
            "sections": [
                {
                    "heading": "1. Information We Collect",
                    "text": "Errors & Performance Data: Captured from your applications. Session Replay Data: User interactions recorded via rrweb. Account Information: Email, name, organization details."
                },
                {
                    "heading": "2. How We Use Information",
                    "text": "To provide error monitoring, performance insights, and debugging tools. To notify users of critical issues or updates. To improve system reliability and security."
                },
                {
                    "heading": "3. Data Storage & Security",
                    "text": "Data is stored in secure databases (Postgres, S3). Access is restricted and encrypted. We do not sell or share personal data with third parties."
                },
                {
                    "heading": "4. User Rights",
                    "text": "You may request deletion of your data. You may opt out of email notifications. You may export your data upon request."
                },
                {
                    "heading": "5. Changes to Policy",
                    "text": "We may update this Privacy Policy. Updates will be posted on our website."
                }
            ]
        }
    }