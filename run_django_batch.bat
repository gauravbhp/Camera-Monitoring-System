cd /d "E:\camera_monitor"
call ".env\Scripts\activate.bat"


:: Then start the server
".env\Scripts\python.exe" manage.py runserver 192.168.3.48:5005
@REM ".env\Scripts\python.exe"  manage.py runserver_plus --cert-file cert.pem 192.168.3.48:5005