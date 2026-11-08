from django.contrib import admin
from .models import Notice, NoticeRead


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'published_by', 'audience_type', 'priority', 'expiry_date', 'created_at']
    list_filter = ['priority', 'audience_type', 'created_at']
    search_fields = ['title', 'content']


@admin.register(NoticeRead)
class NoticeReadAdmin(admin.ModelAdmin):
    list_display = ['notice', 'user', 'read_at']
    list_filter = ['read_at']
