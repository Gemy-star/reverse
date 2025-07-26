from .common import *


INSTALLED_APPS += [
    'silk',
]

MIDDLEWARE += ['silk.middleware.SilkyMiddleware',]

