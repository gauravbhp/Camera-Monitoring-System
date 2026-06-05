# cameras/email_utils.py
import csv
import io
import os
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import threading

def send_offline_camera_report(check_results, check_time=None):
    """
    Send email report with offline cameras
    Returns: success (bool), message (str)
    """
    if not check_time:
        check_time = datetime.now()
    
    # Filter offline cameras
    offline_cameras = []
    for result in check_results:
        if result.get('ping') == 'DOWN':
            offline_cameras.append({
                'name': result['camera']['name'],
                'ip': result['camera']['ip'],
                'location': result['camera']['location'],
                'critical': result['camera']['critical'],
                'timestamp': result['timestamp'],
                'ping': result['ping'],
                'rtsp': result['rtsp'],
                'http': result['http'],
                'https': result['https'],
            })
    
    if not offline_cameras:
        return True, "No offline cameras"
    
    try:
        # Check if email is configured
        email_host = getattr(settings, 'EMAIL_HOST', None)
        if not email_host:
            return False, "Email not configured"
        
        # Create CSV in memory
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        
        # Write header
        writer.writerow([
            'Camera Name', 'IP Address', 'Location', 
            'Priority', 'Status', 'RTSP Port', 'HTTP Port', 
            'HTTPS Port', 'Last Checked'
        ])
        
        # Write data
        for camera in offline_cameras:
            writer.writerow([
                camera['name'],
                camera['ip'],
                camera['location'],
                'CRITICAL' if camera['critical'] == 'YES' else 'NORMAL',
                camera['ping'],
                camera['rtsp'],
                camera['http'],
                camera['https'],
                camera['timestamp']
            ])
        
        # Create email subject
        total_offline = len(offline_cameras)
        critical_offline = sum(1 for c in offline_cameras if c['critical'] == 'YES')
        
        subject = f"Camera Monitor Alert: {total_offline} Cameras Offline"
        if critical_offline > 0:
            subject = f"URGENT: {total_offline} Critical Cameras Offline"
        
        # Create simple email body
        email_body = f"""
Camera Monitoring System Report
===============================

Dashboard URL: http://192.168.3.48:5005/

Check Time: {check_time.strftime("%Y-%m-%d %H:%M:%S")}
Total Cameras Checked: {len(check_results)}
Offline Cameras: {total_offline}

OFFLINE CAMERAS:
"""
        
        for camera in offline_cameras:
            email_body += f"\n- {camera['name']} ({camera['ip']}) - {camera['location']}"
            if camera['critical'] == 'YES':
                email_body += " [CRITICAL]"
        
        email_body += f"""

A CSV file with detailed information is attached.

This is an automated message from Camera Monitoring System.
"""
        
        # Get recipients from settings
        recipients = getattr(settings, 'ALERT_RECIPIENTS', ['ithardware@skapsindia.com'])
        
        # Create email
        email = EmailMessage(
            subject=subject,
            body=email_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            to=recipients,
        )
        
        # Attach CSV
        csv_filename = f"offline_cameras_{check_time.strftime('%Y%m%d_%H%M%S')}.csv"
        email.attach(csv_filename, csv_buffer.getvalue(), 'text/csv')
        
        # Send email
        email.send(fail_silently=True)
        
        print(f" Email sent to {len(recipients)} recipients")
        print(f"   Subject: {subject}")
        print(f"   Attached CSV: {csv_filename} ({total_offline} cameras)")
        
        return True, "Email sent successfully"
        
    except Exception as e:
        print(f" Error sending email: {e}")
        return False, str(e)

def send_test_email():
    """
    Send test email to verify configuration
    """
    try:
        # Check if email is configured
        email_host = getattr(settings, 'EMAIL_HOST', None)
        if not email_host:
            return False
        
        subject = "Camera Monitor Test Email"
        message = f"""
This is a test email from the Camera Monitoring System.

If you're receiving this, your email configuration is working correctly.

System Details:
- Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- Server: Camera Monitoring System

Regards,
Camera Monitoring System
"""
        
        recipients = getattr(settings, 'ALERT_RECIPIENTS', ['ithardware@skapsindia.com'])
        
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            to=recipients,
        )
        
        email.send(fail_silently=True)
        print(" Test email sent successfully")
        return True
        
    except Exception as e:
        print(f" Test email failed: {e}")
        return False