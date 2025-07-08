from enum import Enum

class DefaultSuperUser:
    """Default superuser info"""

    EMAIL = "noreply.admin@reverse-eg.com"
    NAME = "reverse"
    PASSWORD = "admin123456"  # nosec


class Groups(Enum):
    """User groups"""

    ADMIN = "Admin"
    CUSTOMER = "customer"