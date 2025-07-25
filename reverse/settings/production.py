from .common import *
import os

DEBUG = True
ALLOWED_HOSTS = ['reverse-eg.com', 'www.reverse-eg.com', 'localhost', '127.0.0.1','31.97.177.210',]

# Add this setting to be more strict about host validation
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/srv/reverse/django-error.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# Database: MariaDB (MySQL compatible)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'reversedb'),
        'USER': os.getenv('DB_USER', 'reverse'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'Gemy@2803150'),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 60,
    }
}

STATIC_ROOT = os.path.join(BASE_DIR , 'staticfiles')