from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, CollegeSetting


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'is_staff']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('CampusConnect Role & Profile', {'fields': ('role', 'phone', 'profile_picture', 'address', 'date_of_birth')}),
    )


@admin.register(CollegeSetting)
class CollegeSettingAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'college_code', 'phone', 'email', 'updated_at']

    def has_add_permission(self, request):
        # Enforce singleton
        return not CollegeSetting.objects.exists()
