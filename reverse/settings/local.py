from .common import *
DEBUG = True

ALLOWED_HOSTS = [
    'reverse-eg.com',
    'www.reverse-eg.com',
    'localhost',
    '127.0.0.1',
    '31.97.177.210',
]
INSTALLED_APPS += [
    'silk',
]

MIDDLEWARE += ['silk.middleware.SilkyMiddleware',]

