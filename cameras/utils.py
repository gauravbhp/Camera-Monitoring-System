import csv
import subprocess
import socket
from datetime import datetime
import os
from django.conf import settings

def ping(ip):
    """Ping an IP address"""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(settings.PING_TIMEOUT), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except:
        return False

def check_port(ip, port):
    """Check if a port is open"""
    try:
        sock = socket.create_connection((ip, port), timeout=settings.SOCKET_TIMEOUT)
        sock.close()
        return True
    except:
        return False

def read_cameras_from_csv():
    """Read cameras from CSV file"""
    cameras = []
    
    if not os.path.exists(settings.CAMERA_CSV_FILE):
        return cameras
    
    with open(settings.CAMERA_CSV_FILE, 'r', encoding='utf-8-sig') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    # Skip empty lines at the beginning
    while lines and not any(c.isalpha() for c in lines[0]):
        lines.pop(0)
    
    if not lines or len(lines) < 2:
        return cameras
    
    # Parse header
    header_line = lines[0]
    header = [h.strip().lower() for h in header_line.split(',')]
    
    # Find IP column
    ip_column = None
    for alias in ['ip', 'ip address', 'ipaddress']:
        if alias in header:
            ip_column = alias
            break
    
    if not ip_column:
        return cameras
    
    # Process data rows
    for i, line in enumerate(lines[1:], 1):
        values = line.split(',')
        
        # Ensure we have enough values
        while len(values) < len(header):
            values.append('')
        
        # Create dictionary
        cam_data = {}
        for j, h in enumerate(header):
            if j < len(values):
                cam_data[h] = values[j].strip()
            else:
                cam_data[h] = ""
        
        # Get IP address
        ip = cam_data.get(ip_column, '')
        if not ip:
            continue
        
        # Get name
        name = cam_data.get('name', f'Camera_{i}')
        
        # Get location
        location = cam_data.get('location', 'Unknown')
        
        # Get critical status
        critical = cam_data.get('critical', 'YES').upper()
        
        cameras.append({
            'id': i,
            'name': name,
            'ip': ip,
            'location': location,
            'critical': critical,
            'raw_data': cam_data
        })
    
    return cameras

def check_camera_status(camera):
    """Check status of a single camera"""
    ip = camera['ip']
    status = {
        'camera': camera,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'ping': 'DOWN',
        'rtsp': 'N/A',
        'http': 'N/A',
        'https': 'N/A',
    }
    
    # Validate IP format
    ip_parts = ip.split('.')
    if len(ip_parts) != 4 or not all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_parts if part.isdigit()):
        status['ping'] = 'INVALID'
        return status
    
    # Ping check
    if ping(ip):
        status['ping'] = 'UP'
        
        # Port checks
        status['rtsp'] = 'UP' if check_port(ip, settings.PORTS_TO_CHECK['RTSP']) else 'DOWN'
        status['http'] = 'UP' if check_port(ip, settings.PORTS_TO_CHECK['HTTP']) else 'DOWN'
        status['https'] = 'UP' if check_port(ip, settings.PORTS_TO_CHECK['HTTPS']) else 'DOWN'
    
    return status

def check_all_cameras():
    """Check status of all cameras"""
    cameras = read_cameras_from_csv()
    results = []
    
    for camera in cameras:
        status = check_camera_status(camera)
        results.append(status)
    
    return results

def save_status_to_csv(status_results):
    """Save status results to CSV file"""
    if not status_results:
        return
    
    # Prepare data for CSV
    csv_data = []
    for status in status_results:
        csv_data.append({
            'timestamp': status['timestamp'],
            'name': status['camera']['name'],
            'ip': status['camera']['ip'],
            'location': status['camera']['location'],
            'critical': status['camera']['critical'],
            'ping': status['ping'],
            'rtsp': status['rtsp'],
            'http': status['http'],
            'https': status['https'],
        })
    
    # Write to CSV
    write_header = not os.path.exists(settings.STATUS_CSV_FILE) or os.path.getsize(settings.STATUS_CSV_FILE) == 0
    
    with open(settings.STATUS_CSV_FILE, 'a', newline='') as csvfile:
        fieldnames = ['timestamp', 'name', 'ip', 'location', 'critical', 'ping', 'rtsp', 'http', 'https']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if write_header:
            writer.writeheader()
        
        writer.writerows(csv_data)

def get_status_history(limit=50):
    """Get recent status history from CSV"""
    history = []
    
    if not os.path.exists(settings.STATUS_CSV_FILE):
        return history
    
    try:
        with open(settings.STATUS_CSV_FILE, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            
            # Get most recent entries
            for row in reversed(rows[-limit:]):
                history.append(row)
    
    except Exception as e:
        print(f"Error reading status history: {e}")
    
    return history

def get_statistics():
    """Get statistics from status history"""
    cameras = read_cameras_from_csv()
    recent_statuses = get_status_history(limit=100)
    
    if not cameras:
        return {
            'total_cameras': 0,
            'up_cameras': 0,
            'down_cameras': 0,
            'uptime_percentage': 0,
        }
    
    # Get latest status for each camera
    camera_status_map = {}
    for status in reversed(recent_statuses):
        ip = status.get('ip')
        if ip and ip not in camera_status_map:
            camera_status_map[ip] = status.get('ping', 'UNKNOWN')
    
    # Count statuses
    up_count = sum(1 for status in camera_status_map.values() if status == 'UP')
    down_count = sum(1 for status in camera_status_map.values() if status == 'DOWN')
    total = len(cameras)
    
    return {
        'total_cameras': total,
        'up_cameras': up_count,
        'down_cameras': down_count,
        'uptime_percentage': (up_count / total * 100) if total > 0 else 0,
    }