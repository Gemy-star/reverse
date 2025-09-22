from django.utils import translation


class ForceArabicDefaultMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'django_language' not in request.COOKIES:
            translation.activate('ar')
            request.LANGUAGE_CODE = 'ar'
        return self.get_response(request)
