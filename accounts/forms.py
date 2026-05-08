from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SignupForm(UserCreationForm):
    # username = 학번
    username = forms.CharField(label="학번", max_length=150)
    first_name = forms.CharField(label="이름", max_length=30)
    library_code = forms.CharField(label="학생증 도서관 번호", max_length=50)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "library_code", "password1", "password2")
