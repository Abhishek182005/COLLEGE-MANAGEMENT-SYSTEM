"""
Django settings for CampusConnect - College Management System.
Configured for production cloud platforms (Render, Railway, Heroku, etc.)
and seamless local execution.
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    os.environ.get(
        "DJANGO_SECRET_KEY",
        "django-insecure-campusconnect-enterprise-security-smartprof-erp-2026-production-hardened-key-c83f9"
    )
)

# SECURITY WARNING: don't run with debug turned on in production!
IS_CLOUD_DEPLOYMENT = any(k in os.environ for k in ("RENDER", "PORT", "DYNO", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME"))
if "DEBUG" in os.environ:
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t", "yes")
else:
    DEBUG = not IS_CLOUD_DEPLOYMENT

# Allowed Hosts & CSRF Origins
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = [
        "*",
        "localhost",
        "127.0.0.1",
        ".onrender.com",
        ".railway.app",
        ".vercel.app",
        ".pythonanywhere.com",
    ]

csrf_origins_env = os.environ.get("CSRF_TRUSTED_ORIGINS")
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(",") if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        "https://*.onrender.com",
        "https://*.railway.app",
        "https://*.vercel.app",
        "https://*.pythonanywhere.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party apps
    "rest_framework",

    # CampusConnect Apps
    "accounts.apps.AccountsConfig",
    "academics.apps.AcademicsConfig",
    "students.apps.StudentsConfig",
    "faculty.apps.FacultyConfig",
    "attendance.apps.AttendanceConfig",
    "timetable.apps.TimetableConfig",
    "examinations.apps.ExaminationsConfig",
    "assignments.apps.AssignmentsConfig",
    "communication.apps.CommunicationConfig",
    "reports.apps.ReportsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Serve static files in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "campusconnect_core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.user_role_context",
            ],
        },
    },
]

WSGI_APPLICATION = "campusconnect_core.wsgi.application"

# Database configuration: Uses DATABASE_URL (PostgreSQL) if provided by cloud platform,
# otherwise falls back seamlessly to SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise production compression & caching storage
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication redirects
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# REST Framework settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# College branding settings
COLLEGE_NAME = "CampusConnect Institute of Technology"
COLLEGE_CODE = "CCIT-092"
ATTENDANCE_SHORTAGE_THRESHOLD = 75.0  # Alert threshold percentage

# ==========================================
# ENTERPRISE SECURITY & BOT HARDENING
# ==========================================
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# Failed login & security rate limit configuration
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900    # 15 minutes cooldown
CAPTCHA_EXPIRY_SECONDS = 600   # 10 minutes challenge lifetime

# Production Security Headers (when running in cloud on HTTPS)
if not DEBUG and IS_CLOUD_DEPLOYMENT:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
elif os.environ.get('DJANGO_SECURE_SSL', 'False').lower() == 'true':
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
