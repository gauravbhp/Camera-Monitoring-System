#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'camera_monitor.settings')
django.setup()

from cameras.monitor import monitor

print("="*60)
print("STARTING AUTOMATIC CAMERA MONITORING SYSTEM")
print("="*60)
print("\nFeatures:")
print("✓ Auto-starts with Django server")
print(f"✓ Checks cameras every 5 minutes")
print("✓ Saves history to CSV")
print("✓ Web dashboard available")
print("✓ No database required")
print("\n" + "="*60)

# Start monitoring
monitor.start_monitoring()

print("\nMonitoring started!")
print("Web interface: http://127.0.0.1:8000")
print("\nPress Ctrl+C to stop...")

try:
    # Keep running
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nStopping monitor...")
    monitor.stop_monitoring()
    print("Monitor stopped.")