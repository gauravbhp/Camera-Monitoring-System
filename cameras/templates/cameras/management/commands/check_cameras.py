from django.core.management.base import BaseCommand
from cameras.monitor import monitor

class Command(BaseCommand):
    help = 'Run a manual camera check'
    
    def handle(self, *args, **options):
        self.stdout.write("Running manual camera check...")
        results = monitor.check_all_cameras()
        self.stdout.write(self.style.SUCCESS(f"Checked {len(results)} cameras"))