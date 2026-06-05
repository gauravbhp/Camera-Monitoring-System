from django.core.management.base import BaseCommand
from cameras.monitor import monitor

class Command(BaseCommand):
    help = 'Start the camera monitoring service'
    
    def handle(self, *args, **options):
        self.stdout.write("Starting camera monitoring service...")
        monitor.start_monitoring()
        
        try:
            # Keep the command running
            while monitor.is_running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("\nStopping camera monitoring service...")
            monitor.stop_monitoring()