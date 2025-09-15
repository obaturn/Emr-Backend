from django.contrib import admin
from .models import EducationalResource, HealthCampaign


@admin.register(HealthCampaign)
class HealthCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'status', 'start_date', 'end_date', 'participants', 'get_created_by_name']
    list_filter = ['status', 'category', 'start_date', 'end_date']
    search_fields = ['title', 'description', 'target_audience']
    ordering = ['-created_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else "N/A"

    get_created_by_name.short_description = 'Created By'


@admin.register(EducationalResource)
class EducationalResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'category', 'get_author_name', 'publish_date', 'views', 'likes']
    list_filter = ['type', 'category', 'publish_date', 'is_active']
    search_fields = ['title', 'description', 'author__username']
    ordering = ['-publish_date']

    def get_author_name(self, obj):
        return obj.author.get_full_name() if obj.author else "N/A"

    get_author_name.short_description = 'Author'