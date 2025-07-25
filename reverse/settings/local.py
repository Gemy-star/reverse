from .common import *
DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS += [
    'silk',
]

MIDDLEWARE += ['silk.middleware.SilkyMiddleware',]

