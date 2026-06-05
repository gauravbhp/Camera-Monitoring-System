from django.apps import AppConfig
import os
import threading
import time

class CamerasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cameras'

    def ready(self):
        """
        Start camera monitoring ONLY ONCE
        - No duplicate threads
        - Safe with Django reloader
        """

        # ✅ VERY IMPORTANT: prevent double execution
        if os.environ.get("RUN_MAIN") != "true":
            return

        def start_monitor():
            # small delay so Django fully loads
            time.sleep(3)

            from .monitor import monitor

            if monitor.is_running:
                print("Camera monitor already running — skipping start")
                return

            print("\n" + "=" * 60)
            print("INITIALIZING DAILY CAMERA MONITORING SYSTEM")
            print("=" * 60)
            print("• Mode        : DAILY (once per day)")
            print(f"• Cameras     : {len(monitor.cameras)}")
            print(f"• Next check  : {monitor.next_check_time}")
            print("=" * 60 + "\n")

            monitor.start_monitoring()

        # ✅ single background thread
        threading.Thread(target=start_monitor, daemon=True).start()
