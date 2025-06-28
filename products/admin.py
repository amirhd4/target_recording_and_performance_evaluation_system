from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from accounts.admin import ids_allowed
from .models import (
    ProductCategory,
    Product,
    Project,
    Machine,
    ProductionOrder,
    InventoryItem
)


class AccessToItAdminMixin:
        @staticmethod
        def has_module_permission(request):
            if request.user.is_superuser:
                return True
            return request.user.id in ids_allowed

        @staticmethod
        def has_view_permission(request, obj=None):
            if request.user.is_superuser:
                return True
            return request.user.id in ids_allowed

        @staticmethod
        def has_change_permission(request, obj=None):
            if request.user.is_superuser:
                return True
            return request.user.id in ids_allowed

        @staticmethod
        def has_add_permission(request, obj=None):
            if request.user.is_superuser:
                return True
            return request.user.id in ids_allowed

        @staticmethod
        def has_delete_permission(request, obj=None):
            if request.user.is_superuser:
                return True
            return request.user.id in ids_allowed


# برای نمایش بهتر مدل‌هایی که به یکدیگر مرتبط هستند، از Inline استفاده می‌کنیم
class ProductInline(AccessToItAdminMixin, admin.TabularInline):
    """ این کلاس اجازه می‌دهد محصولات مرتبط با یک دسته‌بندی را مستقیماً در صفحه همان دسته‌بندی ببینید و ویرایش کنید. """
    model = Product
    extra = 0  # جلوگیری از نمایش فرم خالی اضافی
    fields = ('name', 'sku', 'is_active')
    show_change_link = True  # لینکی برای رفتن به صفحه ویرایش کامل محصول


@admin.register(ProductCategory)
class ProductCategoryAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'parent', 'product_count')
    search_fields = ('name', 'description')
    list_filter = ('parent',)
    autocomplete_fields = ('parent',)  # برای جستجو و انتخاب آسان‌تر والد

    # برای نمایش بهتر فیلدهای ManyToMany
    filter_horizontal = ('managing_groups',)

    inlines = [ProductInline]  # اضافه کردن اینلاین محصولات

    def get_queryset(self, request):
        # بهینه‌سازی کوئری برای شمارش محصولات
        return super().get_queryset(request).prefetch_related('products')

    @admin.display(description=_("تعداد محصولات"))
    def product_count(self, obj):
        # نمایش تعداد محصولات در هر دسته بدون نیاز به کوئری اضافه در لحظه
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'is_active')
    search_fields = ('name', 'sku', 'description', 'category__name')
    list_filter = ('category', 'is_active')
    autocomplete_fields = ('category',)  # برای جستجو و انتخاب آسان‌تر دسته‌بندی
    list_per_page = 25


@admin.register(Project)
class ProjectAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    search_fields = ('name', 'description')
    list_filter = ('start_date',)
    filter_horizontal = ('related_categories',)  # بهترین نمایش برای فیلدهای ManyToMany


@admin.register(Machine)
class MachineAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'model_number', 'is_operational')
    search_fields = ('name', 'model_number')
    list_filter = ('is_operational',)


@admin.register(ProductionOrder)
class ProductionOrderAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('product', 'project', 'quantity', 'status', 'assigned_to', 'created_at')

    search_fields = ['product__name', 'project__name', "assigned_to__username", "assigned_to__first_name",
                     "assigned_to__last_name"]
    list_filter = ('status', 'project', 'created_at', 'assigned_to')
    autocomplete_fields = ('product', 'project', 'assigned_to', 'machine_used')

    # فیلدهایی که در حالت ویرایش فقط خواندنی هستند
    readonly_fields = ('created_at', 'completed_at')

    # اضافه کردن یک Action برای تغییر وضعیت گروهی سفارشات
    actions = ['mark_as_completed', 'mark_as_in_progress']

    def product(self, obj):
        return ",".join([p for p in obj.products.all()])
    product.short_description = "محصولات"

    def project(self, obj):
        return ",".join([p for p in obj.projects.all()])
    project.short_description = "پروژه ها"

    def assigned_to(self, obj):
        return ",".join([p for p in obj.assigned_to.all()])
    assigned_to.short_description = "اختصاص داده شده به"

    @admin.action(description=_("علامت‌گذاری به عنوان تکمیل شده"))
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status=ProductionOrder.StatusChoices.COMPLETED, completed_at=timezone.now())
        self.message_user(request, _("سفارشات انتخاب شده با موفقیت به 'تکمیل شده' تغییر وضعیت یافتند."))

    @admin.action(description=_("علامت‌گذاری به عنوان در حال انجام"))
    def mark_as_in_progress(self, request, queryset):
        queryset.update(status=ProductionOrder.StatusChoices.IN_PROGRESS)
        self.message_user(request, _("سفارشات انتخاب شده با موفقیت به 'در حال انجام' تغییر وضعیت یافتند."))


@admin.register(InventoryItem)
class InventoryItemAdmin(AccessToItAdminMixin, admin.ModelAdmin):
    list_display = ('product', 'quantity', 'condition', 'last_updated')
    search_fields = ('product__name',)
    list_filter = ('condition', 'product__category')
    autocomplete_fields = ('product',)
    readonly_fields = ('last_updated',)
    list_per_page = 30