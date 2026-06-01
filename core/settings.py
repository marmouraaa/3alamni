from pathlib import Path
from decouple import config, Csv
from dotenv import load_dotenv
import os

# Chargement des variables d'environnement
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────
#  SÉCURITÉ — variables depuis .env
# ─────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='change-me-in-production-please')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

GROQ_API_KEY = config('GROQ_API_KEY', default='')

# ─────────────────────────────────────────────
#  APPLICATIONS
# ─────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'strawberry.django',      # GraphQL
    'accounts',
    'early_warning',
    'health',
    'education',
    'study',
    'parental',
    'dashboard',
    'audit',
    'api',
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

ROOT_URLCONF = 'core.urls'

LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'early_warning': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

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
            ],
        },
    },
]

# ─────────────────────────────────────────────
#  WSGI / ASGI
# ─────────────────────────────────────────────
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# ─────────────────────────────────────────────
#  CHANNELS (WebSocket)
# ─────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# ─────────────────────────────────────────────
#  CACHE — utilisé pour le rate limiting login
# ─────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': '3alemni-cache',
    }
}

# ─────────────────────────────────────────────
#  BASE DE DONNÉES
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ─────────────────────────────────────────────
#  SESSION CONFIGURATION (CORRECTION AJOUTÉE)
# ─────────────────────────────────────────────
# Configuration explicite du moteur de session pour résoudre "Session data corrupted"
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Utilise la base de données

# Configuration des cookies de session
SESSION_COOKIE_HTTPONLY = True   # JS ne peut pas lire le cookie de session
SESSION_COOKIE_SAMESITE = 'Lax'  # Protection CSRF supplémentaire
# SESSION_COOKIE_SECURE = True    # À activer en prod (HTTPS uniquement)

# Expiration des sessions
SESSION_COOKIE_AGE = 1209600  # 2 semaines en secondes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False  # Ne pas sauvegarder à chaque requête

# ─────────────────────────────────────────────
#  CSRF CONFIGURATION
# ─────────────────────────────────────────────
CSRF_COOKIE_HTTPONLY = False     # Django a besoin d'y accéder en JS pour les requêtes fetch
CSRF_COOKIE_SAMESITE = 'Lax'
# CSRF_COOKIE_SECURE = True      # À activer en prod
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'iphone_home'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─────────────────────────────────────────────
#  I18N
# ─────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Tunis'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────
#  FICHIERS STATIQUES & MEDIA
# ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─────────────────────────────────────────────
#  DEFAULT AUTO FIELD
# ─────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'