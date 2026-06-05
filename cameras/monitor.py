import sys
sys.stdout.reconfigure(encoding='utf-8')

import csv
import subprocess
import socket
from datetime import datetime, timedelta, time as dt_time
import os
import threading
import time
import json
import concurrent.futures
import queue
import platform
from django.conf import settings

class CameraMonitor:

    def __init__(self):
        self.cameras = []
        self.latest_results = []
        self.status_history = []
        
        # Thread management
        self.is_running = False
        self.monitor_thread = None
        self.check_thread = None
        self.check_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Check status
        self.last_check_time = None
        self.next_check_time = None
        self.check_in_progress = False
        self.check_count = 0
        self.check_cancelled = False
        
        # Process info
        self.process_id = os.getpid()
        self.lock_file = os.path.join(settings.CSV_DIR, "check_lock.lock")
        
        # Platform info for ping command
        self.system = platform.system().lower()
        
        # Initialize
        self.read_cameras_from_csv()
        self.calculate_next_daily_check()
        self.load_status_cache()
        self.clean_stale_lock(force=True)  # Force clean on startup
        
        print(f"✅ Multi-threaded CameraMonitor READY | PID={self.process_id} | OS={self.system}")

    # ------------------------------------------------------------------
    # THREADED CAMERA CHECKING SYSTEM
    # ------------------------------------------------------------------

    def start_check_thread(self):
        """Start the camera checking thread"""
        if self.check_thread and self.check_thread.is_alive():
            print("⚠️ Check thread already running")
            return
    
        self.check_thread = threading.Thread(target=self._camera_check_worker, daemon=True)
        self.check_thread.start()
        print("✅ Camera check worker thread started")

    def _camera_check_worker(self):
        """Worker thread that processes camera checks from queue"""
        print("✅ Camera check worker started")
        
        while self.is_running:
            try:
                # Wait for check request
                check_request = self.check_queue.get(timeout=1)
                
                if check_request == "STOP":
                    print("🛑 Check worker stopping")
                    break
                
                # Process the check
                self._process_camera_check()
                
                self.check_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Error in check worker: {e}")
                time.sleep(1)

    def _process_camera_check(self):
        """Process camera check in separate thread"""
        # Try to acquire lock with retry
        lock_acquired = False
        for attempt in range(3):
            if self.acquire_lock():
                lock_acquired = True
                break
            print(f"⚠️ Lock acquisition attempt {attempt + 1} failed, retrying in 2 seconds...")
            time.sleep(2)
        
        if not lock_acquired:
            print("❌ Cannot acquire lock after 3 attempts - skipping check")
            # Force clean the lock and try one last time
            self.clean_stale_lock(force=True)
            if not self.acquire_lock():
                print("❌ Still cannot acquire lock - aborting check")
                return
        
        self.check_in_progress = True
        self.check_cancelled = False
        self.check_count += 1
        start_time = time.time()
        
        try:
            print(f"\n🔍 THREADED CHECK #{self.check_count} STARTED at {datetime.now().strftime('%H:%M:%S')}")
            print(f"📊 Checking {len(self.cameras)} cameras...")
            
            # Create results storage
            all_results = []
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Process cameras in parallel batches
            batch_size = 20
            camera_batches = [
                self.cameras[i:i + batch_size] 
                for i in range(0, len(self.cameras), batch_size)
            ]
            
            total_batches = len(camera_batches)
            processed_cameras = 0
            
            for batch_num, batch in enumerate(camera_batches, 1):
                if self.check_cancelled:
                    print("🛑 Check cancelled by user")
                    break
                
                print(f"   📦 Processing batch {batch_num}/{total_batches} ({len(batch)} cameras)")
                
                # Check cameras in this batch in parallel
                batch_results = self._check_camera_batch(batch, ts)
                all_results.extend(batch_results)
                
                processed_cameras += len(batch_results)
                
                # Update intermediate results
                self._update_intermediate_results(all_results)
                
                # Calculate progress
                progress = (processed_cameras / len(self.cameras)) * 100
                print(f"     📈 Progress: {progress:.1f}% ({processed_cameras}/{len(self.cameras)})")
            
            if not self.check_cancelled:
                # Final update
                self.latest_results = all_results
                self.last_check_time = datetime.now()
                self.calculate_next_daily_check()
                
                # Statistics
                elapsed = time.time() - start_time
                up_count = sum(1 for r in all_results if r.get("ping") == "UP")
                down_count = sum(1 for r in all_results if r.get("ping") == "DOWN")
                error_count = sum(1 for r in all_results if r.get("ping") in ["ERROR", "TIMEOUT", "NO_IP"])
                
                print(f"\n📊 FINAL RESULTS:")
                print(f"    ✅ UP: {up_count}")
                print(f"    ❌ DOWN: {down_count}")
                print(f"    ⚠️ ERRORS: {error_count}")
                print(f"    ⏱️ Time: {elapsed:.1f}s ({elapsed/60:.1f}m)")
                if elapsed > 0:
                    print(f"    ⚡ Speed: {len(self.cameras)/elapsed:.1f} cameras/second")
                
                # Save to history
                self._save_to_history(all_results)
                
                # Save to CSV
                self.save_status_to_csv(all_results)
                self.update_status_cache()
                
                # Try to send email notification if there are offline cameras
                if down_count > 0:
                    self._try_send_email_notification(all_results)
                
                print(f"✅ THREADED CHECK #{self.check_count} COMPLETED in {elapsed:.1f}s")
                
                # Notify via result queue
                self.result_queue.put({
                    'type': 'check_complete',
                    'check_id': self.check_count,
                    'results': all_results,
                    'time': elapsed
                })
        
        except Exception as e:
            print(f"❌ ERROR during threaded check: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.check_in_progress = False
            self.release_lock()
            print("🔓 Lock released")

    def _try_send_email_notification(self, results):
        """Try to send email notification if email is configured"""
        try:
            # Check if we have offline cameras
            offline_count = sum(1 for r in results if r.get('ping') == 'DOWN')
            
            if offline_count == 0:
                print("📧 All cameras online - no email needed")
                return
            
            # Try to import email utilities
            try:
                from .email_utils import send_offline_camera_report
            except ImportError as e:
                print(f"📧 Email utilities not available: {e}")
                return
            
            # Check if email is configured in settings
            email_host = getattr(settings, 'EMAIL_HOST', None)
            
            if not email_host:
                print("📧 Email not configured in settings.py")
                return
            
            # Send email notification
            print(f"📧 Sending email for {offline_count} offline cameras...")
            success, message = send_offline_camera_report(results)
            
            if success:
                print(f"✅ Email sent: {message}")
            else:
                print(f"❌ Email failed: {message}")
                
        except Exception as e:
            print(f"❌ Error in email notification: {e}")

    def _check_camera_batch(self, camera_batch, timestamp):
        """Check a batch of cameras in parallel"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all cameras for checking
            future_to_camera = {
                executor.submit(self._check_single_camera, cam, timestamp): cam 
                for cam in camera_batch
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_camera):
                if self.check_cancelled:
                    break
                    
                cam = future_to_camera[future]
                try:
                    status = future.result(timeout=10)
                    results.append(status)
                except concurrent.futures.TimeoutError:
                    print(f"     ⚠️ Timeout checking {cam['name']}")
                    results.append(self._create_timeout_status(cam, timestamp))
                except Exception as e:
                    print(f"     ❌ Error checking {cam['name']}: {e}")
                    results.append(self._create_error_status(cam, timestamp, str(e)))
        
        return results

    def _check_single_camera(self, camera, timestamp):
        """Check a single camera (runs in thread pool)"""
        ip = camera["ip"]
        
        if not ip or ip.strip() == "":
            return self._create_empty_status(camera, timestamp)
        
        # Check ping using proper ICMP ping
        is_up, response_time = self._ping_check(ip)
        
        status = {
            "camera": camera,
            "timestamp": timestamp,
            "ping": "UP" if is_up else "DOWN",
            "response_time": response_time,
            "rtsp": "N/A",
            "http": "N/A",
            "https": "N/A",
        }
        
        # Only check ports if ping succeeded
        if is_up:
            port_results = self._check_ports_parallel(ip)
            status["http"] = port_results.get(80, "DOWN")
            status["rtsp"] = port_results.get(554, "DOWN")
            status["https"] = port_results.get(443, "DOWN")
        
        return status

    def _ping_check(self, ip, timeout=2):
        """
        Proper ICMP ping check that works across platforms
        Returns (is_up, response_time_ms)
        """
        try:
            # Platform-specific ping command
            if self.system == 'windows':
                # Windows ping command
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
            else:
                # Linux/Mac ping command
                cmd = ['ping', '-c', '1', '-W', str(timeout), ip]
            
            # Run ping command
            start_time = time.time()
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=timeout + 1,
                creationflags=subprocess.CREATE_NO_WINDOW if self.system == 'windows' else 0  # Prevent console window on Windows
            )
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check if ping was successful
            if result.returncode == 0:
                return True, round(response_time, 2)
            else:
                return False, None
                
        except subprocess.TimeoutExpired:
            return False, None
        except Exception as e:
            # Silently fail for ping errors
            return False, None

    def _check_ports_parallel(self, ip, ports=[80, 554, 443]):
        """Check multiple ports in parallel"""
        port_results = {}
        
        def check_port(port):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.5)
                result = sock.connect_ex((ip, port))
                sock.close()
                return port, "UP" if result == 0 else "DOWN"
            except:
                return port, "DOWN"
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(check_port, port) for port in ports]
            for future in concurrent.futures.as_completed(futures):
                port, status = future.result()
                port_results[port] = status
        
        return port_results

    def _create_empty_status(self, camera, timestamp):
        """Create status for camera with no IP"""
        return {
            "camera": camera,
            "timestamp": timestamp,
            "ping": "NO_IP",
            "response_time": None,
            "rtsp": "N/A",
            "http": "N/A",
            "https": "N/A",
        }

    def _create_timeout_status(self, camera, timestamp):
        """Create status for timeout"""
        return {
            "camera": camera,
            "timestamp": timestamp,
            "ping": "TIMEOUT",
            "response_time": None,
            "rtsp": "N/A",
            "http": "N/A",
            "https": "N/A",
        }

    def _create_error_status(self, camera, timestamp, error):
        """Create status for error"""
        return {
            "camera": camera,
            "timestamp": timestamp,
            "ping": "ERROR",
            "response_time": None,
            "rtsp": "N/A",
            "http": "N/A",
            "https": "N/A",
            "error": error
        }

    def _update_intermediate_results(self, results):
        """Update intermediate results during check"""
        if results:
            self.latest_results = results
            self.update_status_cache()

    def _save_to_history(self, results):
        """Save results to history"""
        for status in results:
            self.status_history.append({
                'name': status['camera']['name'],
                'ip': status['camera']['ip'],
                'location': status['camera']['location'],
                'critical': status['camera']['critical'],
                'ping': status['ping'],
                'response_time': status.get('response_time'),
                'rtsp': status['rtsp'],
                'http': status['http'],
                'https': status['https'],
                'timestamp': status['timestamp']
            })
        
        # Keep history limited
        if len(self.status_history) > 1000:
            self.status_history = self.status_history[-1000:]

    # ------------------------------------------------------------------
    # PUBLIC INTERFACE
    # ------------------------------------------------------------------

    def start_monitoring(self):
        """Start the monitoring system"""
        if self.is_running:
            print("⚠️ Monitor already running")
            return
        
        self.is_running = True
        
        # Force clean any stale locks
        self.clean_stale_lock(force=True)
        
        # Start the check worker thread
        self.start_check_thread()
        
        # Start the monitor loop thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        print("✅ Monitor system started with separate threads")

    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_running = False
        
        # Signal check worker to stop
        if hasattr(self, 'check_queue'):
            try:
                self.check_queue.put("STOP")
            except:
                pass
        
        # Release lock if held
        self.release_lock()
        
        print("🛑 Monitor system stopping...")

    def check_all_cameras(self):
        """Start a camera check in separate thread"""
        if self.check_in_progress:
            print("⚠️ Check already in progress")
            return {"status": "busy", "message": "Check already running"}
        
        # Force clean lock before queuing
        self.clean_stale_lock(force=True)
        
        # Queue the check request
        try:
            self.check_queue.put("CHECK_NOW")
            return {"status": "queued", "message": "Check queued for execution"}
        except:
            return {"status": "error", "message": "Failed to queue check"}

    def force_check_now(self):
        """Force immediate camera check"""
        print("\n🔴 FORCING IMMEDIATE THREADED CHECK")
        # Force clean lock
        self.clean_stale_lock(force=True)
        return self.check_all_cameras()

    def cancel_check(self):
        """Cancel ongoing camera check"""
        if self.check_in_progress:
            self.check_cancelled = True
            print("🛑 Check cancellation requested")
            return True
        return False

    def get_check_status(self):
        """Get current check status"""
        return {
            "in_progress": self.check_in_progress,
            "cancelled": self.check_cancelled,
            "check_count": self.check_count,
            "last_check": self.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time else None,
            "next_check": self.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.next_check_time else None,
            "cameras_loaded": len(self.cameras),
            "latest_results": len(self.latest_results)
        }

    # ------------------------------------------------------------------
    # MONITOR LOOP
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        """Main monitoring loop - schedules daily checks"""
        print("⏰ Monitor scheduler started")
        
        while self.is_running:
            try:
                now = datetime.now()
                
                if self.next_check_time:
                    wait_seconds = (self.next_check_time - now).total_seconds()
                    
                    if wait_seconds > 0:
                        # Wait for next check time
                        time.sleep(min(wait_seconds, 60))
                        continue
                    else:
                        # Time for scheduled check
                        if not self.check_in_progress:
                            print(f"⏰ Scheduled daily check at {now.strftime('%H:%M:%S')}")
                            self.check_all_cameras()
                        
                        # Calculate next check time
                        self.calculate_next_daily_check()
                else:
                    # No next check time calculated
                    self.calculate_next_daily_check()
                    time.sleep(60)
                    
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")
                time.sleep(60)

    # ------------------------------------------------------------------
    # LOCK HANDLING
    # ------------------------------------------------------------------

    def clean_stale_lock(self, force=False):
        """Remove stale lock files"""
        if os.path.exists(self.lock_file):
            try:
                lock_age = time.time() - os.path.getmtime(self.lock_file)
                
                # Check if lock is from current process
                try:
                    with open(self.lock_file, 'r') as f:
                        lock_pid = int(f.read().strip())
                    if lock_pid == self.process_id and not force:
                        print(f"🔒 Lock owned by current process (PID={lock_pid})")
                        return False
                except:
                    pass
                
                # Force clean or age > 5 minutes
                if force or lock_age > 300:  # 5 minutes
                    print(f"🧹 Cleaning {'forced' if force else 'stale'} lock (age: {lock_age:.0f}s)")
                    os.remove(self.lock_file)
                    return True
                else:
                    print(f"🔒 Lock exists and is recent (age: {lock_age:.0f}s)")
            except Exception as e:
                print(f"⚠️ Error checking lock: {e}")
                try:
                    os.remove(self.lock_file)
                    return True
                except:
                    pass
        return False

    def acquire_lock(self):
        """Acquire check lock"""
        self.clean_stale_lock()
        
        if os.path.exists(self.lock_file):
            return False
        
        try:
            with open(self.lock_file, "x") as f:
                f.write(str(self.process_id))
                f.flush()
            print(f"🔒 Lock acquired (PID={self.process_id})")
            return True
        except Exception as e:
            print(f"⚠️ Failed to acquire lock: {e}")
            return False

    def release_lock(self):
        """Release check lock"""
        try:
            if os.path.exists(self.lock_file):
                # Verify it's our lock
                try:
                    with open(self.lock_file, 'r') as f:
                        lock_pid = int(f.read().strip())
                    if lock_pid == self.process_id:
                        os.remove(self.lock_file)
                        print(f"🔓 Lock released (PID={self.process_id})")
                    else:
                        print(f"⚠️ Lock owned by different process (PID={lock_pid}), not releasing")
                except:
                    # If we can't read it, try to remove anyway
                    os.remove(self.lock_file)
                    print("🔓 Lock forcefully removed")
        except Exception as e:
            print(f"⚠️ Error releasing lock: {e}")

    # ------------------------------------------------------------------
    # UTILITY METHODS
    # ------------------------------------------------------------------

    def calculate_next_daily_check(self):
        """Calculate next scheduled check time"""
        now = datetime.now()
        if getattr(settings, "DAILY_CHECK_TIME", None):
            h, m = map(int, settings.DAILY_CHECK_TIME.split(":"))
            today_time = datetime.combine(now.date(), dt_time(h, m))
            self.next_check_time = today_time if now < today_time else today_time + timedelta(days=1)
        else:
            # Default to next day at same time if no setting
            self.next_check_time = now + timedelta(days=1)
            # Set to 9 AM next day
            self.next_check_time = self.next_check_time.replace(hour=9, minute=0, second=0, microsecond=0)

    def get_monitor_info(self):
        """Get monitor information"""
        return {
            'is_running': self.is_running,
            'last_check': self.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time else 'Never',
            'next_check': self.next_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.next_check_time else 'Not scheduled',
            'check_interval': f"Daily at {getattr(settings, 'DAILY_CHECK_TIME', '09:00')}",
            'check_type': getattr(settings, 'CHECK_TYPE', 'DAILY'),
            'total_cameras': len(self.cameras),
            'time_until_next': self._get_time_until_next_check(),
            'check_in_progress': self.check_in_progress,
            'check_cancelled': self.check_cancelled,
            'check_count': self.check_count,
        }

    def _get_time_until_next_check(self):
        """Get time until next check as string"""
        if not self.next_check_time:
            return "Not scheduled"
        now = datetime.now()
        if self.next_check_time > now:
            time_diff = self.next_check_time - now
            minutes = int(time_diff.total_seconds() // 60)
            seconds = int(time_diff.total_seconds() % 60)
            return f"{minutes}m {seconds}s"
        else:
            return "Now"

    def get_status_history(self, limit=100):
        """Get status history"""
        if not self.status_history:
            return []
        actual_limit = min(limit, len(self.status_history))
        return self.status_history[-actual_limit:]

    def get_statistics(self):
        """Get statistics"""
        stats = {
            'total_cameras': len(self.cameras),
            'up_cameras': 0,
            'down_cameras': 0,
            'no_ip_cameras': 0,
            'timeout_cameras': 0,
            'error_cameras': 0,
            'uptime_percentage': 0,
        }
        
        for status in self.latest_results:
            ping_status = status.get('ping', 'UNKNOWN')
            if ping_status == 'UP':
                stats['up_cameras'] += 1
            elif ping_status == 'DOWN':
                stats['down_cameras'] += 1
            elif ping_status == 'NO_IP':
                stats['no_ip_cameras'] += 1
            elif ping_status == 'TIMEOUT':
                stats['timeout_cameras'] += 1
            elif ping_status == 'ERROR':
                stats['error_cameras'] += 1
        
        if stats['total_cameras'] > 0:
            stats['uptime_percentage'] = (stats['up_cameras'] / stats['total_cameras']) * 100
        
        return stats

    # ------------------------------------------------------------------
    # CSV READING METHODS
    # ------------------------------------------------------------------

    def read_cameras_from_csv(self):
        """Read cameras from CSV - handles encoding issues properly"""
        self.cameras = []
        
        csv_file = settings.CAMERA_CSV_FILE
        print(f"📁 Reading CSV: {csv_file}")
        
        if not os.path.exists(csv_file):
            print(f"❌ File not found: {csv_file}")
            return
        
        # Try different encodings
        encodings_to_try = ['utf-8-sig', 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
        
        for encoding in encodings_to_try:
            try:
                print(f"\n📄 Trying encoding: {encoding}")
                self._read_csv_with_encoding(csv_file, encoding)
                
                if self.cameras:
                    print(f"✅ Successfully loaded {len(self.cameras)} cameras using {encoding} encoding")
                    return
                else:
                    print(f"⚠️ No cameras loaded with {encoding}, trying next encoding...")
                    
            except Exception as e:
                print(f"❌ Failed with {encoding}: {e}")
                continue
        
        # If all encodings fail, try binary reading
        print("\n⚠️ All encodings failed, trying binary reading...")
        self._read_csv_binary(csv_file)

    def _read_csv_with_encoding(self, csv_file, encoding):
        """Read CSV with specific encoding"""
        self.cameras = []
        
        with open(csv_file, 'r', encoding=encoding, errors='replace') as f:
            # Read first few lines to check
            first_lines = []
            for i in range(5):
                line = f.readline()
                if line:
                    first_lines.append(line.strip())
            
            print(f"📄 First 3 lines with {encoding}:")
            for i, line in enumerate(first_lines[:3]):
                print(f"  Line {i+1}: {line}")
            
            # Go back to start and read properly
            f.seek(0)
            
            # Try to detect delimiter
            first_line = f.readline().strip()
            f.seek(0)
            
            delimiter = ','
            if ',' in first_line:
                delimiter = ','
            elif ';' in first_line:
                delimiter = ';'
            elif '\t' in first_line:
                delimiter = '\t'
            
            print(f"📌 Using delimiter: {repr(delimiter)}")
            
            # Read CSV
            reader = csv.DictReader(f, delimiter=delimiter)
            
            if not reader.fieldnames:
                print("⚠️ No headers found")
                return
            
            print(f"📋 Headers: {reader.fieldnames}")
            
            row_count = 0
            for row in reader:
                row_count += 1
                
                # Extract data - handle various field names
                name = ''
                ip = ''
                location = ''
                critical = 'YES'
                
                # Find name field
                for key in ['Name', 'name', 'NAME', 'Camera', 'camera']:
                    if key in row:
                        name = str(row[key]).strip()
                        break
                
                # Find IP field
                for key in ['Ip', 'ip', 'IP', 'IP Address', 'IP_ADDRESS']:
                    if key in row:
                        ip = str(row[key]).strip()
                        break
                
                # Find location field
                for key in ['Location', 'location', 'LOCATION', 'Site', 'site']:
                    if key in row:
                        location = str(row[key]).strip()
                        break
                
                # Find critical field
                for key in ['Critical', 'critical', 'CRITICAL', 'Priority', 'priority']:
                    if key in row:
                        critical = str(row[key]).strip().upper()
                        break
                
                # Generate name if empty
                if not name:
                    name = f"Camera{row_count}"
                
                # Clean critical value
                if critical not in ['YES', 'NO']:
                    if critical.lower() in ['yes', 'y', 'true', '1', 'critical', 'high']:
                        critical = 'YES'
                    else:
                        critical = 'NO'
                
                # Add to list even if IP is empty (we'll handle it later)
                self.cameras.append({
                    "id": row_count,
                    "name": name,
                    "ip": ip,
                    "location": location if location else "Unknown",
                    "critical": critical,
                })
                
                if row_count <= 3:
                    print(f"  Sample row {row_count}: '{name}' -> '{ip}'")
                elif row_count == 100 or row_count == 500:
                    print(f"  Row {row_count}: '{name}' -> '{ip}'")
            
            print(f"📊 Loaded {len(self.cameras)} rows")

    def _read_csv_binary(self, csv_file):
        """Read CSV file in binary mode and clean it"""
        print("📁 Reading CSV in binary mode...")
        
        try:
            # Read binary data
            with open(csv_file, 'rb') as f:
                binary_data = f.read()
            
            print(f"📊 Binary size: {len(binary_data)} bytes")
            
            # Replace non-breaking spaces (0xa0) with regular spaces (0x20)
            cleaned_data = binary_data.replace(b'\xa0', b' ')
            
            # Try to decode with different encodings
            decoded_text = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    decoded_text = cleaned_data.decode(encoding)
                    print(f"✅ Decoded with {encoding}")
                    break
                except:
                    continue
            
            if not decoded_text:
                # Force decode with errors replaced
                decoded_text = cleaned_data.decode('utf-8', errors='replace')
                print("⚠️ Forced decode with error replacement")
            
            # Parse the decoded text
            lines = decoded_text.split('\n')
            
            print(f"📄 Total lines in cleaned file: {len(lines)}")
            
            # Simple parsing
            self.cameras = []
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Skip if looks like header
                if i == 0 and ('name' in line.lower() or 'ip' in line.lower()):
                    continue
                
                # Try different delimiters
                if ',' in line:
                    parts = [part.strip() for part in line.split(',')]
                elif ';' in line:
                    parts = [part.strip() for part in line.split(';')]
                elif '\t' in line:
                    parts = [part.strip() for part in line.split('\t')]
                else:
                    parts = [line.strip()]
                
                # Extract data
                name = parts[0] if len(parts) > 0 else f"Camera{i}"
                ip = parts[1] if len(parts) > 1 else ""
                location = parts[2] if len(parts) > 2 else "Unknown"
                critical = parts[3].upper() if len(parts) > 3 else "YES"
                
                if critical not in ['YES', 'NO']:
                    critical = 'YES'
                
                self.cameras.append({
                    "id": len(self.cameras) + 1,
                    "name": name,
                    "ip": ip,
                    "location": location,
                    "critical": critical,
                })
            
            print(f"✅ Binary method loaded {len(self.cameras)} cameras")
                    
        except Exception as e:
            print(f"❌ Binary reading failed: {e}")

    def save_status_to_csv(self, results):
        """Save status results to CSV"""
        if not results:
            return
        
        try:
            new = not os.path.exists(settings.STATUS_CSV_FILE)
            with open(settings.STATUS_CSV_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if new:
                    writer.writerow(["timestamp","name","ip","location","critical","ping","response_time_ms","rtsp","http","https"])
                
                for r in results:
                    writer.writerow([
                        r["timestamp"],
                        r["camera"]["name"],
                        r["camera"]["ip"],
                        r["camera"]["location"],
                        r["camera"]["critical"],
                        r["ping"],
                        r.get("response_time", ""),
                        r["rtsp"],
                        r["http"],
                        r["https"],
                    ])
            
            print(f"💾 Saved {len(results)} results to CSV")
        except Exception as e:
            print(f"❌ Error saving CSV: {e}")

    def update_status_cache(self):
        """Update status cache file"""
        try:
            cache_file = os.path.join(settings.CSV_DIR, "status_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "last_check": str(self.last_check_time) if self.last_check_time else None,
                    "next_check": str(self.next_check_time) if self.next_check_time else None,
                    "running": self.check_in_progress,
                    "cameras_count": len(self.cameras),
                    "latest_results_count": len(self.latest_results),
                    "check_count": self.check_count,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error updating status cache: {e}")

    def load_status_cache(self):
        """Load status cache from file"""
        cache_file = os.path.join(settings.CSV_DIR, "status_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    print(f"📦 Loaded status cache from previous run")
            except:
                pass

#  GLOBAL INSTANCE
monitor = CameraMonitor()