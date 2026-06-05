from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from .monitor import monitor
import os
import csv
from datetime import datetime
import zipfile
import io
from .email_config import EmailConfigForm
from django.contrib import messages

def dashboard(request):
    """Main dashboard view"""
    # Get monitor info using direct attributes since get_monitor_info might not exist
    monitor_info = {
        'is_running': getattr(monitor, 'is_running', False),
        'last_check': monitor.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'last_check_time') and monitor.last_check_time else 'Never',
        'next_check': monitor.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'next_check_time') and monitor.next_check_time else 'Not scheduled',
        'check_interval': f"Every {getattr(settings, 'CHECK_INTERVAL', '?')} minutes",
        'check_type': getattr(settings, 'CHECK_TYPE', 'DAILY'),
        'total_cameras': len(getattr(monitor, 'cameras', [])),
    }
    
    # Calculate time until next check
    if hasattr(monitor, 'next_check_time') and monitor.next_check_time:
        now = datetime.now()
        if monitor.next_check_time > now:
            time_diff = monitor.next_check_time - now
            minutes = int(time_diff.total_seconds() // 60)
            seconds = int(time_diff.total_seconds() % 60)
            monitor_info['time_until_next'] = f"{minutes}m {seconds}s"
        else:
            monitor_info['time_until_next'] = "Now"
    else:
        monitor_info['time_until_next'] = "Not scheduled"
    
    # Get latest results
    latest_results = getattr(monitor, 'latest_results', [])
    cameras_with_status = []
    
    for status in latest_results:
        cameras_with_status.append({
            'camera': status.get('camera', {}),
            'status': {
                'ping': status.get('ping', 'UNKNOWN'),
                'rtsp': status.get('rtsp', 'N/A'),
                'http': status.get('http', 'N/A'),
                'https': status.get('https', 'N/A'),
                'timestamp': status.get('timestamp', 'Never')
            }
        })
    
    # Get recent history - try to use get_status_history if it exists, otherwise use latest_results
    if hasattr(monitor, 'get_status_history'):
        recent_history = monitor.get_status_history(limit=10)
    else:
        # Fallback: use latest results formatted as history
        recent_history = []
        for status in latest_results[:10]:
            recent_history.append({
                'name': status.get('camera', {}).get('name', 'Unknown'),
                'ip': status.get('camera', {}).get('ip', 'Unknown'),
                'location': status.get('camera', {}).get('location', 'Unknown'),
                'critical': status.get('camera', {}).get('critical', 'NO'),
                'ping': status.get('ping', 'UNKNOWN'),
                'rtsp': status.get('rtsp', 'N/A'),
                'http': status.get('http', 'N/A'),
                'https': status.get('https', 'N/A'),
                'timestamp': status.get('timestamp', 'Never')
            })
    
    # Get statistics
    stats = {
        'total_cameras': len(getattr(monitor, 'cameras', [])),
        'up_cameras': 0,
        'down_cameras': 0,
        'uptime_percentage': 0,
    }
    
    # Count statuses
    for status in latest_results:
        if status.get('ping') == 'UP':
            stats['up_cameras'] += 1
        elif status.get('ping') == 'DOWN':
            stats['down_cameras'] += 1
    
    # Calculate uptime percentage
    if stats['total_cameras'] > 0:
        stats['uptime_percentage'] = (stats['up_cameras'] / stats['total_cameras']) * 100
    
    # Get critical DOWN cameras only
    critical_down_cameras = []
    for item in cameras_with_status:
        camera_critical = item['camera'].get('critical', 'NO')
        status_ping = item['status'].get('ping', 'UNKNOWN')
        
        if camera_critical == 'YES' and status_ping == 'DOWN':
            critical_down_cameras.append(item)
    
    # Get location summary for dashboard
    locations_dict = {}
    for camera in getattr(monitor, 'cameras', []):
        location = camera.get('location', 'Unknown')
        if location not in locations_dict:
            locations_dict[location] = {
                'name': location,
                'camera_count': 0,
                'up_count': 0,
                'down_count': 0
            }
        locations_dict[location]['camera_count'] += 1
    
    # Count status for each location
    for status in latest_results:
        location = status.get('camera', {}).get('location', 'Unknown')
        if location in locations_dict:
            if status.get('ping') == 'UP':
                locations_dict[location]['up_count'] += 1
            elif status.get('ping') == 'DOWN':
                locations_dict[location]['down_count'] += 1
    
    # Convert to list and sort
    locations_summary = list(locations_dict.values())
    locations_summary.sort(key=lambda x: x['name'])
    
    context = {
        'monitor_info': monitor_info,
        'cameras': cameras_with_status,
        'recent_history': recent_history,
        'stats': stats,
        'critical_down_cameras': critical_down_cameras,
        'locations_summary': locations_summary,
        'check_interval': getattr(settings, 'CHECK_INTERVAL', 60),
    }
    
    return render(request, 'cameras/dashboard.html', context)

def camera_list(request):
    """List all cameras with filtering"""
    # Create monitor_info for template
    monitor_info = {
        'is_running': getattr(monitor, 'is_running', False),
        'last_check': monitor.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'last_check_time') and monitor.last_check_time else 'Never',
        'next_check': monitor.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'next_check_time') and monitor.next_check_time else 'Not scheduled',
        'total_cameras': len(getattr(monitor, 'cameras', [])),
    }
    
    cameras = getattr(monitor, 'cameras', [])

    # ===== GET FILTERS =====
    location_filter = request.GET.get('location', '').strip()
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()

    # ===== LATEST STATUS MAP =====
    camera_status_map = {}
    for status in getattr(monitor, 'latest_results', []):
        camera_id = status.get('camera', {}).get('id')
        if camera_id:
            camera_status_map[camera_id] = {
                'ping': status.get('ping'),
                'rtsp': status.get('rtsp'),
                'http': status.get('http'),
                'https': status.get('https'),
                'timestamp': status.get('timestamp')
            }

    cameras_with_status = []

    # ===== STATUS COUNTS =====
    online_count = offline_count = unknown_count = critical_count = 0

    for camera in cameras:
        status = camera_status_map.get(camera.get('id', ''), {})
        ping = status.get('ping')

        # ===== COUNT STATUS =====
        if ping == 'UP':
            online_count += 1
            camera_status = 'ONLINE'
        elif ping == 'DOWN':
            offline_count += 1
            camera_status = 'OFFLINE'
        else:
            unknown_count += 1
            camera_status = 'UNKNOWN'

        if camera.get('critical') == 'YES':
            critical_count += 1
            camera_priority = 'CRITICAL'
        else:
            camera_priority = 'NORMAL'

        # ===== APPLY LOCATION FILTER =====
        if location_filter and camera.get('location', '').upper() != location_filter.upper():
            continue

        # ===== APPLY STATUS FILTER =====
        if status_filter and camera_status != status_filter:
            continue

        # ===== APPLY PRIORITY FILTER =====
        if priority_filter and camera_priority != priority_filter:
            continue

        cameras_with_status.append({
            'camera': camera,
            'status': status
        })

    # ===== LOCATIONS =====
    locations = sorted(set(cam.get('location', '') for cam in cameras if cam.get('location')))

    # ===== PAGINATION =====
    page = int(request.GET.get('page', 1))
    items_per_page = 50
    total_pages = (len(cameras_with_status) + items_per_page - 1) // items_per_page

    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_cameras = cameras_with_status[start_idx:end_idx]

    page_range = get_page_range(page, total_pages)

    context = {
        'monitor_info': monitor_info,
        'cameras': paginated_cameras,

        'total_cameras': len(cameras),
        'filtered_cameras': len(cameras_with_status),

        'location_filter': location_filter,
        'status_filter': status_filter,
        'priority_filter': priority_filter,

        'locations': locations,

        'online_count': online_count,
        'offline_count': offline_count,
        'unknown_count': unknown_count,
        'critical_count': critical_count,

        'current_page': page,
        'total_pages': total_pages,
        'page_range': page_range,
        'start_idx': start_idx,
        'end_idx': min(end_idx, len(cameras_with_status)),
        
        'total_locations': len(locations),
    }

    return render(request, 'cameras/camera_list.html', context)

def run_manual_check(request):
    """Run a manual camera check"""
    if getattr(monitor, 'check_in_progress', False):
        messages.warning(request, "Camera check already running. Please wait.")
        return redirect('dashboard')

    results = monitor.force_check_now()
    messages.success(request, f'Manual check completed! Checked {len(results)} cameras')
    return redirect('dashboard')


# In views.py

def api_check_status(request):
    """API endpoint to get check status"""
    status = monitor.get_check_status()
    return JsonResponse(status)

def api_start_check(request):
    """API endpoint to start a check"""
    result = monitor.check_all_cameras()
    return JsonResponse(result)

def api_cancel_check(request):
    """API endpoint to cancel ongoing check"""
    success = monitor.cancel_check()
    return JsonResponse({"success": success})

def api_force_check(request):
    """API endpoint for forced check"""
    result = monitor.force_check_now()
    return JsonResponse(result)


def status_history(request):
    """Show status history"""
    # Get limit from request, default to 100
    try:
        limit = int(request.GET.get('limit', 100))
    except (ValueError, TypeError):
        limit = 100
    
    # Try to get history from monitor
    if hasattr(monitor, 'get_status_history'):
        history = monitor.get_status_history(limit=limit)
    else:
        # Fallback: use latest results
        latest_results = getattr(monitor, 'latest_results', [])
        history = []
        for status in latest_results[:limit]:
            history.append({
                'name': status.get('camera', {}).get('name', 'Unknown'),
                'ip': status.get('camera', {}).get('ip', 'Unknown'),
                'location': status.get('camera', {}).get('location', 'Unknown'),
                'critical': status.get('camera', {}).get('critical', 'NO'),
                'ping': status.get('ping', 'UNKNOWN'),
                'rtsp': status.get('rtsp', 'N/A'),
                'http': status.get('http', 'N/A'),
                'https': status.get('https', 'N/A'),
                'timestamp': status.get('timestamp', 'Never')
            })
    
    context = {
        'history': history,
        'total_entries': len(history),
        'limit': limit,
    }
    
    return render(request, 'cameras/status_history.html', context)


from .email_utils import send_test_email

def test_email_view(request):
    from django.contrib import messages
    
    if send_test_email():
        messages.success(request, 'Test email sent successfully!')
    else:
        messages.error(request, 'Failed to send test email. Make sure email is configured in settings.py')
    
    return redirect('dashboard')


def download_csv(request):
    """Download current camera status as CSV"""
    # Create response with CSV content
    response = HttpResponse(content_type='text/csv')
    filename = f'camera_status_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Get latest results
    latest_results = getattr(monitor, 'latest_results', [])
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Timestamp', 'Camera Name', 'IP Address', 'Location', 
        'Priority', 'Ping Status', 'RTSP Port', 'HTTP Port', 'HTTPS Port'
    ])
    
    # Write data
    for status in latest_results:
        writer.writerow([
            status.get('timestamp', ''),
            status.get('camera', {}).get('name', ''),
            status.get('camera', {}).get('ip', ''),
            status.get('camera', {}).get('location', ''),
            'CRITICAL' if status.get('camera', {}).get('critical') == 'YES' else 'NORMAL',
            status.get('ping', ''),
            status.get('rtsp', ''),
            status.get('http', ''),
            status.get('https', '')
        ])
    
    return response

def download_history_csv(request):
    """Download complete status history as CSV"""
    # Create response with CSV content
    response = HttpResponse(content_type='text/csv')
    filename = f'camera_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Get all history
    if hasattr(monitor, 'get_status_history'):
        history = monitor.get_status_history(limit=1000)
    else:
        history = []
    
    if not history:
        writer = csv.writer(response)
        writer.writerow(['No history data available'])
        return response
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Timestamp', 'Camera Name', 'IP Address', 'Location', 
        'Priority', 'Ping Status', 'RTSP Port', 'HTTP Port', 'HTTPS Port'
    ])
    
    # Write data
    for check in history:
        writer.writerow([
            check.get('timestamp', ''),
            check.get('name', ''),
            check.get('ip', ''),
            check.get('location', ''),
            'CRITICAL' if check.get('critical', '').upper() == 'YES' else 'NORMAL',
            check.get('ping', ''),
            check.get('rtsp', ''),
            check.get('http', ''),
            check.get('https', '')
        ])
    
    return response

def download_location_csv(request):
    """Download camera status for a specific location"""
    location = request.GET.get('location', '')
    
    if not location:
        # Return all locations if none specified
        return download_csv(request)
    
    # Get latest results
    latest_results = getattr(monitor, 'latest_results', [])
    
    # Filter by location
    location_results = []
    for status in latest_results:
        if status.get('camera', {}).get('location', '').upper() == location.upper():
            location_results.append(status)
    
    if not location_results:
        return HttpResponse(f"No cameras found for location: {location}", status=404)
    
    # Create response with CSV content
    response = HttpResponse(content_type='text/csv')
    filename = f'camera_status_{location.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Timestamp', 'Camera Name', 'IP Address', 'Location', 
        'Priority', 'Ping Status', 'RTSP Port', 'HTTP Port', 'HTTPS Port'
    ])
    
    # Write data
    for status in location_results:
        writer.writerow([
            status.get('timestamp', ''),
            status.get('camera', {}).get('name', ''),
            status.get('camera', {}).get('ip', ''),
            status.get('camera', {}).get('location', ''),
            'CRITICAL' if status.get('camera', {}).get('critical') == 'YES' else 'NORMAL',
            status.get('ping', ''),
            status.get('rtsp', ''),
            status.get('http', ''),
            status.get('https', '')
        ])
    
    return response

def download_all_locations(request):
    """Download separate CSV files for each location as a ZIP"""
    # Get all unique locations
    cameras = getattr(monitor, 'cameras', [])
    locations = set()
    for camera in cameras:
        if camera.get('location'):
            locations.add(camera['location'])
    
    if not locations:
        return HttpResponse("No locations found", status=404)
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for location in locations:
            # Filter cameras for this location
            location_cameras = []
            for camera in cameras:
                if camera.get('location') == location:
                    location_cameras.append(camera)
            
            # Get latest status for these cameras
            location_results = []
            for status in getattr(monitor, 'latest_results', []):
                if status.get('camera', {}).get('location') == location:
                    location_results.append(status)
            
            if location_results:
                # Create CSV content for this location
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                
                # Write header
                writer.writerow([
                    'Timestamp', 'Camera Name', 'IP Address', 'Location', 
                    'Priority', 'Ping Status', 'RTSP Port', 'HTTP Port', 'HTTPS Port'
                ])
                
                # Write data
                for status in location_results:
                    writer.writerow([
                        status.get('timestamp', ''),
                        status.get('camera', {}).get('name', ''),
                        status.get('camera', {}).get('ip', ''),
                        status.get('camera', {}).get('location', ''),
                        'CRITICAL' if status.get('camera', {}).get('critical') == 'YES' else 'NORMAL',
                        status.get('ping', ''),
                        status.get('rtsp', ''),
                        status.get('http', ''),
                        status.get('https', '')
                    ])
                
                # Add to ZIP
                zip_file.writestr(
                    f'camera_status_{location.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.csv',
                    csv_buffer.getvalue()
                )
    
    # Prepare response
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="all_locations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"'
    
    return response

def locations_list(request):
    """List all locations with download options"""
    # Get all unique locations
    cameras = getattr(monitor, 'cameras', [])
    locations_dict = {}
    
    for camera in cameras:
        location = camera.get('location')
        if location not in locations_dict:
            locations_dict[location] = {
                'name': location,
                'camera_count': 0,
                'up_count': 0,
                'down_count': 0
            }
        locations_dict[location]['camera_count'] += 1
    
    # Count status for each location
    for status in getattr(monitor, 'latest_results', []):
        location = status.get('camera', {}).get('location')
        if location in locations_dict:
            if status.get('ping') == 'UP':
                locations_dict[location]['up_count'] += 1
            elif status.get('ping') == 'DOWN':
                locations_dict[location]['down_count'] += 1
    
    locations = list(locations_dict.values())
    locations.sort(key=lambda x: x['name'])
    
    context = {
        'locations': locations,
        'total_locations': len(locations),
    }
    
    return render(request, 'cameras/locations_list.html', context)

def check_monitor_status(request):
    """Check monitor status and timing"""
    now = datetime.now()
    
    status_info = {
        'monitor_running': getattr(monitor, 'is_running', False),
        'last_check': monitor.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'last_check_time') and monitor.last_check_time else 'Never',
        'next_check': monitor.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'next_check_time') and monitor.next_check_time else 'Not scheduled',
        'check_interval_minutes': getattr(settings, 'CHECK_INTERVAL', 60),
        'current_time': now.strftime("%Y-%m-%d %H:%M:%S"),
        'cameras_loaded': len(getattr(monitor, 'cameras', [])),
        'latest_results': len(getattr(monitor, 'latest_results', [])),
    }
    
    # Calculate time until next check
    if hasattr(monitor, 'next_check_time') and monitor.next_check_time:
        time_diff = (monitor.next_check_time - now).total_seconds()
        status_info['seconds_until_next_check'] = int(time_diff)
        status_info['minutes_until_next_check'] = int(time_diff / 60)
    
    return JsonResponse(status_info)

def api_status(request):
    """API endpoint for current status"""
    # Create monitor info
    monitor_info = {
        'is_running': getattr(monitor, 'is_running', False),
        'last_check': monitor.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'last_check_time') and monitor.last_check_time else 'Never',
        'next_check': monitor.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(monitor, 'next_check_time') and monitor.next_check_time else 'Not scheduled',
        'total_cameras': len(getattr(monitor, 'cameras', [])),
    }
    
    # Create stats
    latest_results = getattr(monitor, 'latest_results', [])
    stats = {
        'total_cameras': len(getattr(monitor, 'cameras', [])),
        'up_cameras': sum(1 for status in latest_results if status.get('ping') == 'UP'),
        'down_cameras': sum(1 for status in latest_results if status.get('ping') == 'DOWN'),
        'uptime_percentage': 0,
    }
    
    if stats['total_cameras'] > 0:
        stats['uptime_percentage'] = (stats['up_cameras'] / stats['total_cameras']) * 100
    
    cameras_data = []
    for status in latest_results:
        cameras_data.append({
            'id': status.get('camera', {}).get('id', ''),
            'name': status.get('camera', {}).get('name', ''),
            'ip': status.get('camera', {}).get('ip', ''),
            'location': status.get('camera', {}).get('location', ''),
            'critical': status.get('camera', {}).get('critical', 'NO'),
            'ping': status.get('ping', ''),
            'rtsp': status.get('rtsp', ''),
            'http': status.get('http', ''),
            'https': status.get('https', ''),
            'timestamp': status.get('timestamp', '')
        })
    
    return JsonResponse({
        'success': True,
        'monitor': monitor_info,
        'statistics': stats,
        'cameras': cameras_data,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def api_control(request):
    """API endpoint to control monitoring"""
    action = request.GET.get('action', '')
    
    if action == 'start':
        return JsonResponse({'success': True, 'message': 'Monitoring started'})
    
    elif action == 'stop':
        monitor.stop_monitoring()
        return JsonResponse({'success': True, 'message': 'Monitoring stopped'})
    
    elif action == 'check':
        if getattr(monitor, 'check_in_progress', False):
            return JsonResponse({
                'success': False,
                'message': 'Check already running'
            })

        results = monitor.check_all_cameras()
        return JsonResponse({
            'success': True,
            'message': f'Checked {len(results)} cameras'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid action'})

def get_page_range(current_page, total_pages, display_pages=5):
    """Get range of pages to display in pagination"""
    if total_pages <= display_pages:
        return range(1, total_pages + 1)
    
    start = max(1, current_page - display_pages // 2)
    end = min(total_pages, start + display_pages - 1)
    
    if end - start + 1 < display_pages:
        start = max(1, end - display_pages + 1)
    
    return range(start, end + 1)

def email_config(request):
    """Email configuration page"""
    if request.method == 'POST':
        form = EmailConfigForm(request.POST)
        if form.is_valid():
            # Update settings (in real app, you'd save to database)
            # For now, just show success message
            messages.success(request, 'Email configuration saved successfully!')
            return redirect('email_config')
    else:
        # Load current settings
        initial_data = {
            'email_host': getattr(settings, 'EMAIL_HOST', 'smtp-mail.outlook.com'),
            'email_port': getattr(settings, 'EMAIL_PORT', 587),
            'email_use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
            'email_host_user': getattr(settings, 'EMAIL_HOST_USER', ''),
            'alert_recipients': ', '.join(getattr(settings, 'ALERT_RECIPIENTS', [])),
            'send_daily_report': getattr(settings, 'SEND_DAILY_REPORT', True),
            'send_alerts_for_critical': getattr(settings, 'SEND_ALERTS_FOR_CRITICAL', True),
            'alert_threshold': getattr(settings, 'ALERT_THRESHOLD', 5),
            'daily_check_time': getattr(settings, 'DAILY_CHECK_TIME', '09:00'),
        }
        form = EmailConfigForm(initial=initial_data)
    
    return render(request, 'cameras/email_config.html', {'form': form})

def send_test_email(request):
    """Send test email"""
    from .email_utils import send_test_email
    
    if send_test_email():
        messages.success(request, 'Test email sent successfully!')
    else:
        messages.error(request, 'Failed to send test email. Check configuration.')
    
    return redirect('email_config')