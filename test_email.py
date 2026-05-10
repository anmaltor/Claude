#!/usr/bin/env python3
"""Test SMTP connection to Gmail."""

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp(config_path: str) -> None:
    """Test SMTP connection and send a test email."""
    with open(config_path) as f:
        config = json.load(f)

    email_config = config.get("notifier_config", {}).get("email", {})

    if not email_config:
        print("[ERROR] No email config found")
        return

    smtp_host = email_config.get("smtp_host")
    smtp_port = email_config.get("smtp_port", 587)
    smtp_user = email_config.get("smtp_user")
    smtp_pass = email_config.get("smtp_password")
    from_addr = email_config.get("from_address", smtp_user)
    to_addrs = email_config.get("to_addresses", [])

    print(f"SMTP Test Configuration:")
    print(f"  Host: {smtp_host}")
    print(f"  Port: {smtp_port}")
    print(f"  User: {smtp_user}")
    print(f"  To: {to_addrs}")
    print()

    try:
        print("[1/4] Connecting to SMTP server...")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            print(f"      [OK] Connected to {smtp_host}:{smtp_port}")

            print("[2/4] Starting TLS encryption...")
            server.starttls()
            print("      [OK] TLS started")

            print("[3/4] Logging in...")
            server.login(smtp_user, smtp_pass)
            print(f"      [OK] Logged in as {smtp_user}")

            print("[4/4] Sending test email...")
            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = "[TEST] Condensation Monitor Email Test"
            msg.attach(MIMEText("This is a test email from the condensation monitoring system.\n\nIf you received this, email delivery is working correctly!", "plain"))

            server.sendmail(from_addr, to_addrs, msg.as_string())
            print("      [OK] Test email sent successfully")

    except smtplib.SMTPAuthenticationError as e:
        print(f"[ERROR] Authentication failed: {e}")
        print("        Check: Gmail app password is correct")
        print("        Check: 2-factor authentication is enabled")

    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error: {e}")

    except TimeoutError:
        print(f"[ERROR] Connection timeout")
        print("        Check: Firewall allows outbound SMTP (port 587)")
        print("        Check: Network connection is available")

    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("        Check: Firewall/VPN settings")
        print("        Check: Gmail account settings")

    print("\nResult: Check the email address above for the test message")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python test_email.py <config.json>")
        sys.exit(1)

    test_smtp(sys.argv[1])
