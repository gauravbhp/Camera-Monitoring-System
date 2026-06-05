import os

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-i#+u*z=tem36zj%%*wf3s4yo$fgcn@#g6%*o678s8&ukh87%rm'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cameras',
    'django_extensions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'camera_monitor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'camera_monitor.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Camera monitoring settings
CSV_DIR = BASE_DIR  # Project root directory
CAMERA_CSV_FILE = os.path.join(BASE_DIR, 'cameras_fixed.csv')  # cameras.csv in project root
STATUS_CSV_FILE = os.path.join(BASE_DIR, 'status_history.csv')

os.makedirs(CSV_DIR, exist_ok=True)

PING_TIMEOUT = 1000  # ms
SOCKET_TIMEOUT = 3
PORTS_TO_CHECK = {
    "RTSP": 554,
    "HTTP": 80,
    "HTTPS": 443
}
CHECK_INTERVAL = 1440  # 1440 minutes = 24 hours (once per day)
# Or set specific time for daily check:
DAILY_CHECK_TIME = "08:00"  # Check at 9:00 AM daily



EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-mail.outlook.com'  # For Outlook/Hotmail
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'itintern@skapsindia.com'  # Your Outlook email
EMAIL_HOST_PASSWORD = 'dfskwymybrvbvdft'  
DEFAULT_FROM_EMAIL = 'itintern@skapsindia.com'

# Alert recipients
ALERT_RECIPIENTS = [
    'ithardware@skapsindia.com',  # Send to yourself
    # 'alkesh.abhani@skapsindia.com'
    # "it.intern@skapsindia.com"
]

# Email settings
SEND_DAILY_REPORT = True  # Send daily report email
SEND_ALERTS_FOR_CRITICAL = True  # Send immediate alerts for critical cameras
ALERT_THRESHOLD = 5
# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
