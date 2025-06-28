from django.contrib import admin
from django.db import models
from jalali_date_new.fields import JalaliDateTimeField
from jalali_date_new.widgets import AdminJalaliDateTimeWidget
from .models import Target
from jalali_date import datetime2jalali
from .models import Target, TaskType # TaskType را اضافه کنید

ids_allowed = [55]

@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.DateTimeField: {
            'form_class': JalaliDateTimeField,
            'widget': AdminJalaliDateTimeWidget,
        },
    }
    
    list_display = ("user_full_name", "jalali_submission_date", "short_content")
    search_fields = ("user__first_name", "user__last_name", "content", "submission_date")
    list_filter = ("submission_date",)
    ordering = ("-submission_date",)

    def jalali_submission_date(self, obj):
        return datetime2jalali(obj.submission_date).strftime('%Y/%m/%d - %H:%M')
    jalali_submission_date.short_description = "تاریخ ثبت"

    def user_full_name(self, obj):
        return obj.user.get_full_name() if obj.user else "---"
    user_full_name.short_description = "کاربر"

    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    short_content.short_description = "متن هدف"


@admin.register(TaskType)
class TaskTypeAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'unit', 'order', 'is_active', 'data_type')
    list_filter = ('group', 'is_active', "data_type")
    search_fields = ('title', "data_type")

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed