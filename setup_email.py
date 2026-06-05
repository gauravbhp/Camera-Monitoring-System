#!/usr/bin/env python
import os
import sys

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'camera_monitor.settings')

import django
django.setup()

from cameras.email_utils import send_test_email

print("="*60)
print("EMAIL CONFIGURATION SETUP")
print("="*60)

print("\nCurrent Configuration:")
print(f"EMAIL_HOST: {os.environ.get('EMAIL_HOST', 'Not set')}")
print(f"EMAIL_PORT: {os.environ.get('EMAIL_PORT', 'Not set')}")
print(f"EMAIL_HOST_USER: {os.environ.get('EMAIL_HOST_USER', 'Not set')}")

print("\n1. Sending test email...")
if send_test_email():
    print("✓ Test email sent successfully!")
    print("✓ Email configuration is working.")
else:
    print("✗ Failed to send test email.")
    print("\nTroubleshooting:")
    print("1. Check your email credentials in settings.py")
    print("2. For Gmail: Enable 2FA and create app password")
    print("3. Check SMTP server settings")
    print("4. Verify network connectivity")

print("\n" + "="*60)