from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
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
    list_display = ['name', 'short_name', 'college_code', 'attendance_threshold', 'logo_display', 'phone', 'email', 'updated_at']
    readonly_fields = ['logo_preview_large', 'updated_at']
    fieldsets = (
        ('Institutional Identity', {
            'fields': ('name', 'short_name', 'college_code', 'tagline', 'established_year')
        }),
        ('Emblem & Branding', {
            'fields': ('logo', 'logo_preview_large', 'logo_url', 'footer_text'),
            'description': 'Upload a college logo image file or specify an external image URL.'
        }),
        ('Academic & Statutory Policies', {
            'fields': ('attendance_threshold', 'principal_name', 'affiliation'),
            'description': 'Configure the dynamic minimum attendance threshold (%) required for examination eligibility across all student dashboards and shortage reports.'
        }),
        ('Contact & Verification Information', {
            'fields': ('address', 'email', 'phone', 'website', 'updated_at')
        }),
    )

    def logo_display(self, obj):
        url = obj.effective_logo_url
        if url:
            return format_html('<img src="{}" style="width: 28px; height: 28px; object-fit: contain; border-radius: 4px; border: 1px solid #ddd; background: #fff;" />', url)
        return "No Logo"
    logo_display.short_description = "Logo"

    def logo_preview_large(self, obj):
        url = obj.effective_logo_url
        if url:
            return format_html('<div style="margin-bottom: 8px;"><img src="{}" style="max-width: 140px; max-height: 140px; object-fit: contain; border-radius: 8px; border: 1px solid #ccc; padding: 4px; background: #fff;" /><br><small style="color: #666;">Current Active Emblem</small></div>', url)
        return "No logo uploaded or configured yet."
    logo_preview_large.short_description = "Emblem Preview"

    def has_add_permission(self, request):
        # Enforce singleton
        return not CollegeSetting.objects.exists()
