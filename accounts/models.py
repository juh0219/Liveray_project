from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    library_code = models.CharField("학생증 도서관 번호", max_length=50, unique=True)

    def __str__(self):
        return f"{self.user.username} ({self.library_code})"
