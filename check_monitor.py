#!/usr/bin/env python
import os
import sys
from datetime import datetime

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'camera_monitor.settings')

import django
django.setup()

from cameras.monitor import monitor

print("="*60)
print("DAILY CHECK SCHEDULE")
print("="*60)

print(f"\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if monitor.last_check_time:
    print(f"Last daily check: {monitor.last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Calculate days since last check
    days_since = (datetime.now() - monitor.last_check_time).days
    hours_since = (datetime.now() - monitor.last_check_time).seconds // 3600
    
    if days_since > 0:
        print(f"Time since last check: {days_since} days, {hours_since} hours")
    else:
        print(f"Time since last check: {hours_since} hours")
else:
    print("Last daily check: Never")

if monitor.next_check_time:
    print(f"Next daily check: {monitor.next_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Calculate time until next check
    time_until = monitor.next_check_time - datetime.now()
    hours = time_until.total_seconds() // 3600
    minutes = (time_until.total_seconds() % 3600) // 60
    
    if hours > 0:
        print(f"Time until next check: {int(hours)} hours, {int(minutes)} minutes")
    else:
        print(f"Time until next check: {int(minutes)} minutes")
else:
    print("Next daily check: Not scheduled")

print(f"\nCameras loaded: {len(monitor.cameras)}")
print(f"Latest results: {len(monitor.latest_results)}")

print("\n" + "="*60)