from rest_framework import serializers
from .models import Notice


class NoticeSerializer(serializers.ModelSerializer):
    publisher_name = serializers.CharField(source='published_by.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Notice
        fields = [
            'id', 'title', 'content', 'published_by', 'publisher_name',
            'audience_type', 'department', 'department_name', 'semester', 'batch',
            'priority', 'attachment', 'expiry_date', 'created_at', 'is_expired'
        ]
