import os
import secrets
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48)
DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [item.strip() for item in os.getenv("ALLOWED_HOSTS", "*").split(",") if item.strip()]

CSRF_TRUSTED_ORIGINS = [
    item.strip() for item in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if item.strip()
]
CSRF_TRUSTED_ORIGINS += [
    "https://*.manus.computer",
    "https://*.manus.space",
]
CSRF_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax" if DEBUG else "None"
SESSION_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "katalog.apps.KatalogConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "kostcerdas.urls"
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
            ],
        },
    },
]

WSGI_APPLICATION = "kostcerdas.wsgi.application"
ASGI_APPLICATION = "kostcerdas.asgi.application"


def database_from_environment():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

    parsed = urlsplit(database_url)
    if parsed.scheme in {"mysql", "mysql+pymysql"}:
        import pymysql

        pymysql.install_as_MySQLdb()
        query = parse_qs(parsed.query)
        options: dict[str, object] = {"charset": "utf8mb4"}
        ssl_value = query.get("ssl", [""])[0].lower()
        if ssl_value in {"1", "true", "yes", "required", "require"}:
            options["ssl"] = {"check_hostname": True}
        return {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": unquote(parsed.path.lstrip("/")),
                "USER": unquote(parsed.username or ""),
                "PASSWORD": unquote(parsed.password or ""),
                "HOST": parsed.hostname or "",
                "PORT": str(parsed.port or 3306),
                "OPTIONS": options,
                "CONN_MAX_AGE": 60,
                "CONN_HEALTH_CHECKS": True,
            }
        }

    if parsed.scheme == "sqlite":
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": unquote(parsed.path),
            }
        }

    raise RuntimeError("DATABASE_URL harus memakai skema mysql:// atau sqlite://.")


DATABASES = database_from_environment()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
