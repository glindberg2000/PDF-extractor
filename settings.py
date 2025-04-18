import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "django-insecure-test-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mydatabase",
        "USER": "newuser",
        "PASSWORD": "newpassword",
        "HOST": "localhost",
        "PORT": "5433",
    }
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "profiles",
]

MIGRATION_MODULES = {
    "profiles": "profiles.migrations",
}
