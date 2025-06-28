from django.contrib import admin
from jalali_date import datetime2jalali

from .models import CustomUser, MonthlyScore, DailyManagerScore, UserResponsibility, UserKnowledgeManagement, \
    RegulationDocument, UserRegulationAcknowledgement, UserOverallRegulationAcknowledgement
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin

ids_allowed = [28, 55]

@admin.register(MonthlyScore)
class MonthlyScoreAdmin(admin.ModelAdmin):
    list_display = ('scorer', 'target', 'score_type', 'value', 'year', 'month')
    list_filter = ('score_type', 'year', 'month')
    search_fields = ('scorer__username', 'target__username')


@admin.register(DailyManagerScore)
class DailyManagerScoreAdmin(admin.ModelAdmin):
    list_display = ('manager', 'employee', 'value', 'date')
    list_filter = ('date',)
    search_fields = ('manager__username', 'employee__username')


class UserResponsibilityInline(admin.TabularInline):
    model = UserResponsibility
    extra = 1
    fields = ('responsibility_type', 'description', 'order')

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        # اجازه اضافه کردن داده شود فقط اگر کاربر لاگین شده در لیست مجاز است.
        # obj در اینجا شیء CustomUser والد است که در حال ویرایش آن هستیم (parent_obj)
        return request.user.id in ids_allowed

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return obj is not None
        # اجازه تغییر داده شود فقط اگر کاربر لاگین شده در لیست مجاز است
        # و obj مشخص است (در حال ویرایش یک نمونه شرح وظیفه خاص هستیم).
        return (request.user.id in ids_allowed) and (obj is not None)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return obj is not None
         # اجازه حذف داده شود فقط اگر کاربر لاگین شده در لیست مجاز است
         # و obj مشخص است (در حال ویرایش یک نمونه شرح وظیفه خاص هستیم).
        return (request.user.id in ids_allowed) and (obj is not None)


    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        # اجازه مشاهده داده شود فقط اگر کاربر لاگین شده در لیست مجاز است.
        # obj در اینجا یک نمونه شرح وظیفه است یا None در حالت لیست Inline ها.
        return request.user.id in ids_allowed


@admin.register(RegulationDocument)
class RegulationDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'file', 'is_active', 'uploaded_at', 'order')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    list_editable = ('is_active', 'order')

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

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed


@admin.register(UserRegulationAcknowledgement)
class UserRegulationAcknowledgementAdmin(admin.ModelAdmin):
    list_display = ('user', 'regulation', 'is_read', 'read_at')
    list_filter = ('is_read', 'regulation')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'regulation__title')
    readonly_fields = ('read_at',)


@admin.register(UserOverallRegulationAcknowledgement)
class UserOverallRegulationAcknowledgementAdmin(admin.ModelAdmin):
    list_display = ('user', 'all_regulations_confirmed', 'confirmation_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('confirmation_date',)

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed


class UserKnowledgeManagementInline(admin.TabularInline):
    model = UserKnowledgeManagement
    extra = 1 # تعداد فرم های خالی اضافه
    # فیلدهایی که می خواهید در Inline نمایش داده شوند و قابل ویرایش باشند
    # فیلد created_at_jalali معمولاً auto_now_add است و در فرم نمایش داده نمی شود
    fields = ('content',) # اگر فیلد order را اضافه کردید: ('content', 'order')
    # نمایش فقط خواندنی فیلدهایی که نباید ویرایش شوند (مثل تاریخ ثبت)
    readonly_fields = ('created_at_jalali',) # فیلد تاریخ ثبت را فقط خواندنی کنید


class UserKnowledgeManagementAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_preview', 'created_at_jalali') # فیلدهایی که در لیست نمایش داده می شوند
    list_filter = ('created_at_jalali', 'user') # فیلترها
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'content') # فیلدهای جستجو
    # فیلدی برای نمایش خلاصه محتوا در لیست (نیاز به تعریف متد در این کلاس دارد)
    def content_preview(self, obj):
        # نمایش 50 کاراکتر اول محتوا یا یک پیام پیش فرض
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = "خلاصه محتوا"


class CustomGroupAdmin(BaseGroupAdmin): # ارث‌بری از BaseGroupAdmin
    def has_add_permission(self, request):
        """کنترل اینکه آیا کاربر می تواند گروه جدید اضافه کند."""
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed

    def has_change_permission(self, request, obj=None):
        """کنترل اینکه آیا کاربر می تواند گروه موجود را تغییر دهد."""
        if request.user.is_superuser:
            return True
        # اجازه تغییر به کاربران مجاز داده شود
        return request.user.id in ids_allowed

    def has_delete_permission(self, request, obj=None):
        """کنترل اینکه آیا کاربر می تواند گروه موجود را حذف کند."""
        if request.user.is_superuser:
            return True
        # اجازه حذف به کاربران مجاز داده شود
        return request.user.id in ids_allowed

    def has_view_permission(self, request, obj=None):
        """کنترل اینکه آیا کاربر می تواند گروه ها را مشاهده کند."""
        if request.user.is_superuser:
            return True
        # اجازه مشاهده به کاربران مجاز داده شود
        return request.user.id in ids_allowed

    def has_module_permission(self, request):
        """کنترل دسترسی به ماژول گروه ها در سایدبار ادمین."""
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed


class CustomUserAdmin(UserAdmin):
    # ... تنظیمات فعلی list_display, list_filter, search_fields, fieldsets (اگر BaseUserAdmin را استفاده کرده بودید)
    # مثال تنظیمات پایه (اگر از BaseUserAdmin استفاده نکردید و CustomUser از AbstractUser ارث می برد):
    list_display = ("id", 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined_jalali', 'last_login', 'access_level', 'supervisor', "sex")
    def date_joined_jalali(self, obj):
        return datetime2jalali(obj.date_joined).strftime('%Y/%m/%d - %H:%M')
    date_joined_jalali.short_description = 'تاریخ عضویت'
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'access_level', "sex") # اضافه کردن access_level
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',) # مرتب سازی پیش فرض
    filter_horizontal = ('groups', 'user_permissions',) # برای مدیریت گروه ها و مجوزها
    # تعریف fieldsets با توجه به AbstractUser (اگر از BaseUserAdmin استفاده نکردید)
    fieldsets = (
        ("احراز هویت", {'fields': ('username', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email', "sex")}),
        ('مجوزها', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تاریخ های مهم', {'fields': ('last_login', 'date_joined')}),
        ('اطلاعات سفارشی', {'fields': ('access_level', 'supervisor')}), # فیلدهای سفارشی شما
    )

    inlines = [UserResponsibilityInline, UserKnowledgeManagementInline]

    def has_module_permission(self, request):
        """کنترل دسترسی به اپلیکیشن در سایدبار ادمین."""
        if request.user.is_superuser:
            return True
        # دسترسی داده شود فقط اگر کاربر لاگین شده در لیست ID های مجاز است
        return request.user.id in ids_allowed


    def get_queryset(self, request):
        """فیلتر کردن لیست کاربرانی که در صفحه لیست کاربران نمایش داده می شوند."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # اگر کاربر لاگین شده در لیست ID های مجاز است، لیست کامل کاربران را ببیند.
        if (request.user.id in ids_allowed):
            return qs # بازگرداندن تمام کاربران
        # در غیر این صورت، لیستی خالی ببیند
        return qs.none()


    def has_change_permission(self, request, obj=None):
        """کنترل اینکه آیا کاربر می تواند یک شیء کاربر خاص را ویرایش/مشاهده کند."""
        if request.user.is_superuser:
            return True
        # اگر obj is None است (کاربر در حال مشاهده لیست تغییرات است)، get_queryset دسترسی را کنترل کرده است.
        # اجازه مشاهده صفحه لیست داده شود اگر دسترسی به ماژول وجود دارد.
        if obj is None:
             return self.has_module_permission(request)

        # اگر obj مشخص است (در حال ویرایش یک کاربر خاص هستیم)
        # اجازه ویرایش/مشاهده صفحه جزئیات داده شود فقط اگر کاربر لاگین شده در لیست ID های مجاز است.
        # اینکه چه فیلدهایی قابل تغییرند، توسط get_fieldsets کنترل می شود.
        return (request.user.id in ids_allowed)


    def get_fieldsets(self, request, obj=None):
        """کنترل اینکه چه فیلدهایی در صفحه ویرایش کاربر نمایش داده شوند."""
        # اگر کاربر سوپریوزر است، فیلدست های استاندارد را نمایش دهید
        if request.user.is_superuser:
             return super().get_fieldsets(request, obj)

        # اگر کاربر لاگین شده در لیست ID های مجاز است (و سوپریوزر نیست)
        if request.user.id in ids_allowed:
            if obj is None:
                # *** Case: Adding a new user ***
                # Get the standard add user fieldsets from UserAdmin
                add_fieldsets = super().get_fieldsets(request, obj)
                filtered_add_fieldsets = []
                # Define fields that these users *should not* see/edit on the add form
                denied_fields_on_add = ['is_staff', 'is_superuser', 'user_permissions', 'last_login', 'date_joined']

                # Iterate through standard add fieldsets and filter out denied fields
                for name, info in add_fieldsets:
                    new_fields = []
                    for field in info['fields']:
                         # Handle tuples like ('field1', 'field2')
                         if isinstance(field, (list, tuple)):
                            new_group = tuple(f for f in field if f not in denied_fields_on_add)
                            if new_group: # Only add the group if it's not empty after filtering
                                new_fields.append(new_group)
                         elif field not in denied_fields_on_add:
                            new_fields.append(field)
                    # Keep the fieldset if it has any allowed fields remaining
                    if new_fields:
                        new_info = info.copy()
                        new_info['fields'] = tuple(new_fields)
                        filtered_add_fieldsets.append((name, new_info))
                return filtered_add_fieldsets
            else:
                # *** Case: Changing an existing user ***
                # Display only specific fields + the inlines are automatically added below these fieldsets
                if request.user.id == 55:
                    if obj.access_level >= -1:
                        allowed_fields = ('username', 'is_active', "password")
                    else:
                        allowed_fields = tuple()
                    return (
                         (None, {'fields': allowed_fields}), # Allow changing username and activation status
                         ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email', "supervisor", "access_level", "groups", "sex")}),
                    )
                else:
                    # I want to tell you, I gonna you
                    return (
                        ('اطلاعات شخصی',
                         {'fields': ('first_name', 'last_name', 'email')}),
                    # Allow changing personal info
                        # Note: password field is not included here for change, UserAdmin handles "change password" link if needed,
                        # but likely you don't want these users changing passwords.
                        # access_level, supervisor, is_staff, is_superuser, groups, user_permissions are hidden.
                    )

        # برای حالاتی که کاربر نه سوپریوزر است و نه در لیست مجاز
        # Based on has_module_permission and get_queryset, they shouldn't reach here,
        # but as a fallback, return empty fieldsets.
        return ()
    
    
    def has_add_permission(self, request):
        """کنترل اینکه آیا کاربر می تواند کاربر جدید اضافه کند."""
        if request.user.is_superuser:
            return True
        return request.user.id in ids_allowed


admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserKnowledgeManagement, UserKnowledgeManagementAdmin)
admin.site.register(UserResponsibility)