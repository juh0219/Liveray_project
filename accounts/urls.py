from django.urls import path
from .views import SignUpView, my_page

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("me/", my_page, name="my_page"),
]