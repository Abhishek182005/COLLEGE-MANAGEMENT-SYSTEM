from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'entity_type', 'entity_id', 'ip_address']
    list_filter = ['action', 'entity_type', 'timestamp']
    search_fields = ['action', 'details', 'user__username', 'ip_address']
    readonly_fields = ['timestamp', 'user', 'action', 'entity_type', 'entity_id', 'details', 'ip_address']

    def has_add_permission(self, request):
        return False  # Immutable security audit records
