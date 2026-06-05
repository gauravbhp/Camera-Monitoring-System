from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('cameras/', views.camera_list, name='camera_list'),
    path('check/', views.run_manual_check, name='run_check'),
    path('history/', views.status_history, name='status_history'),
    path('locations/', views.locations_list, name='locations_list'),
    path('email-config/', views.email_config, name='email_config'),
    path('send-test-email/', views.send_test_email, name='send_test_email'),
    
    # Download endpoints
    path('download/csv/', views.download_csv, name='download_csv'),
    path('download/history/', views.download_history_csv, name='download_history'),
    path('download/location/', views.download_location_csv, name='download_location'),
    path('download/all-locations/', views.download_all_locations, name='download_all_locations'),
    
    # Status endpoints
    path('monitor-status/', views.check_monitor_status, name='monitor_status_check'),
    
    # API endpoints
    path('api/status/', views.api_status, name='api_status'),
    path('api/control/', views.api_control, name='api_control'),
    
    path('test-email/', views.test_email_view, name='test_email'),
    
    path('api/check/status/', views.api_check_status, name='api_check_status'),
    path('api/check/start/', views.api_start_check, name='api_start_check'),
    path('api/check/cancel/', views.api_cancel_check, name='api_cancel_check'),
    path('api/check/force/', views.api_force_check, name='api_force_check'),
    
    # Add monitor_status back
    path('monitor/', views.dashboard, name='monitor_status'),
]