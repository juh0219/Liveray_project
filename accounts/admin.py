from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "추가 정보(프로필)"


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "first_name", "library_code", "is_staff", "is_active")
    search_fields = ("username", "first_name", "profile__library_code")
    list_filter = ("is_staff", "is_active")

    @admin.display(description="도서관 번호")
    def library_code(self, obj):
        return getattr(obj.profile, "library_code", "")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
