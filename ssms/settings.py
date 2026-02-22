"""
Django settings for ssms project.
"""

from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# --------------------------------------------------
# BASE DIR
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------
# SECURITY
# --------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False") == "True"


raw_allowed_hosts = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [host.strip() for host in raw_allowed_hosts.split(",") if host.strip()]

# Keep local development usable when ALLOWED_HOSTS is not configured in .env.
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0"]

raw_csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in raw_csrf_origins.split(",") if origin.strip()
]

# Backward-compatible fallback: derive https origins from ALLOWED_HOSTS when explicit
# CSRF_TRUSTED_ORIGINS is not provided.
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}"
        for host in ALLOWED_HOSTS
        if host not in {"127.0.0.1", "localhost", "0.0.0.0"}
    ]


# --------------------------------------------------
# APPLICATIONS
# --------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'storages',   # ✅ added for R2

    'ssmsapp',
    'django_extensions',
    'widget_tweaks',
]


# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# --------------------------------------------------
# URL / WSGI
# --------------------------------------------------
ROOT_URLCONF = 'ssms.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'ssmsapp.context_processors.notice_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'ssms.wsgi.application'


# --------------------------------------------------
# DATABASE
# --------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --------------------------------------------------
# PASSWORD VALIDATION
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# --------------------------------------------------
# MEDIA FILES (LOCAL DEV)
# --------------------------------------------------
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# --------------------------------------------------
# CLOUD STORAGE (Cloudflare R2)
# --------------------------------------------------
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "").strip()

# Allow users to paste endpoint as https://<id>.r2.cloudflarestorage.com
R2_ENDPOINT_URL = R2_ENDPOINT_URL.replace("<", "").replace(">", "")

# Prevent startup crash when endpoint is still a placeholder like <accountid>.
R2_CONFIG_VALID = all([R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET_NAME, R2_ENDPOINT_URL]) and "accountid" not in R2_ENDPOINT_URL.lower()

if R2_CONFIG_VALID:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = R2_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_REGION_NAME = "auto"
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


# --------------------------------------------------
# DEFAULT PK
# --------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --------------------------------------------------
# RAZORPAY
# --------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

