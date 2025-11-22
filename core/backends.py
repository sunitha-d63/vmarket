from django.contrib.auth.backends import ModelBackend
from core.models import CustomUser

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None

        email = username.strip().lower()

        try:
            user = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return None

        if user.check_password(password):
            return user

        return None
