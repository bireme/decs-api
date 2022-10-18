from tastypie.models import ApiKey
from tastypie.http import HttpUnauthorized
from tastypie.authentication import Authentication
from django.core.exceptions import ObjectDoesNotExist

class CustomApiKeyAuthentication(Authentication):
    """
    Handles API key auth, in which a user provides an API key.
    Uses the ``ApiKey`` model that ships with tastypie.
    """

    def _unauthorized(self):
        return HttpUnauthorized()

    def extract_credentials(self, request):
        authorization = request.META.get('HTTP_AUTHORIZATION', '')

        if not authorization:
            api_key = request.GET.get('api_key') or request.POST.get('api_key')
        else:
            api_key = request.META.get('HTTP_AUTHORIZATION', '')

        return api_key

    def is_authenticated(self, request, **kwargs):
        """
        Finds the user and checks their API key.

        Should return either ``True`` if allowed, ``False`` if not or an
        ``HttpResponse`` if you need something custom.
        """
        try:
            api_key = self.extract_credentials(request)
        except ValueError:
            return self._unauthorized()

        if not api_key:
            return self._unauthorized()

        key_auth_check = self.get_key(api_key, request)
        return key_auth_check

    def get_key(self, api_key, request):
        """
        Attempts to find the API key for the user. Uses ``ApiKey`` by default
        but can be overridden.
        """
        from tastypie.models import ApiKey

        try:
            user = ApiKey.objects.get(key=api_key)
        except ObjectDoesNotExist:
            return self._unauthorized()
        return True

"""
    def get_identifier(self, request):
        try:
            username = self.extract_credentials(request)[0]
        except ValueError:
            username = ''
        return username or 'nouser'
"""

