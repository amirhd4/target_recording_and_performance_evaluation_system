from django.db import models
from django.contrib.auth.models import Group
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _


# --- مدل‌های پایه و دسته‌بندی ---
class ProductCategory(models.Model):
    """
    دسته‌بندی اصلی محصولات (مثال: ODF، پچ پنل، پیگتیل).
    این مدل جایگزین بهتری برای استفاده از Group جنگو برای دسته بندی محصولات است.
    """
    name = models.CharField(max_length=200, verbose_name=_("نام دسته‌بندی"))
    description = models.TextField(blank=True, null=True, verbose_name=_("توضیحات"))
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("دسته‌بندی والد")
    )
    # اضافه کردن فیلد واحد برای دسته‌بندی
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("واحد شمارش (مثال: عدد، متر)")
    )
    # اتصال اختیاری به گروه‌های کاربری جنگو برای مدیریت دسترسی
    managing_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='product_categories',
        verbose_name=_("گروه‌های کاربری مجاز")
    )

    class Meta:
        verbose_name = _("دسته‌بندی محصول")
        verbose_name_plural = _("دسته‌بندی‌های محصولات")
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    تعریف یک محصول خاص (مثال: پچ پنل فیبر نوری 24 پورت SC داپلکس).
    """
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT, # جلوگیری از حذف دسته‌بندی‌ای که محصول دارد
        related_name='products',
        verbose_name=_("دسته‌بندی")
    )
    name = models.CharField(max_length=255, verbose_name=_("نام محصول"))
    sku = models.CharField(max_length=100, unique=True, verbose_name=_("کد محصول (SKU)"))
    description = models.TextField(blank=True, null=True, verbose_name=_("مشخصات فنی"))
    is_active = models.BooleanField(default=True, verbose_name=_("فعال"))

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")
        ordering = ['category', 'name']

    def __str__(self):
        # تغییر در نمایش رشته‌ای برای خوانایی بهتر در Select2
        return f"{self.name} ({self.sku}) - {self.category.name}"


class Project(models.Model):
    """
    مدیریت پروژه‌های شرکت. هر پروژه می‌تواند محصولات خاص خود را داشته باشد.
    """
    name = models.CharField(max_length=255, unique=True, verbose_name=_("نام پروژه"))
    description = models.TextField(blank=True, null=True, verbose_name=_("توضیحات پروژه"))
    start_date = models.DateField(verbose_name=_("تاریخ شروع"))
    end_date = models.DateField(null=True, blank=True, verbose_name=_("تاریخ پایان"))
    # مشخص می‌کند چه نوع محصولاتی در این پروژه تعریف می‌شوند
    related_categories = models.ManyToManyField(
        ProductCategory,
        related_name='projects',
        blank=True,
        verbose_name=_("دسته‌بندی‌های مرتبط")
    )

    class Meta:
        verbose_name = _("پروژه")
        verbose_name_plural = _("پروژه‌ها")
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def has_active_production_orders(self):
        """
        بررسی می‌کند آیا این پروژه سفارش تولیدی در وضعیت 'در انتظار شروع' یا 'در حال انجام' دارد.
        """
        return self.production_orders.filter(
            status__in=['PENDING', 'IN_PROGRESS']
        ).exists()


# --- مدل‌های فرآیند و وضعیت ---
class Machine(models.Model):
    """
    مدل برای ثبت ماشین‌آلات و تجهیزات تولید.
    """
    name = models.CharField(max_length=150, verbose_name=_("نام دستگاه"))
    model_number = models.CharField(max_length=100, blank=True, verbose_name=_("مدل"))
    is_operational = models.BooleanField(default=True, verbose_name=_("آماده به کار"))

    class Meta:
        verbose_name = _("ماشین/تجهیزات")
        verbose_name_plural = _("ماشین‌آلات و تجهیزات")

    def __str__(self):
        return self.name


class ProductionOrder(models.Model):
    """
    مدل اصلی برای ردیابی فرآیند تولید یا انجام یک کار.
    اینجا وضعیت‌های مختلف (معلق، در حال انجام و...) مدیریت می‌شوند.
    """
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _("در انتظار شروع")
        IN_PROGRESS = 'IN_PROGRESS', _("در حال ساخت/انجام")
        COMPLETED = 'COMPLETED', _("تکمیل شده")
        SUSPENDED = 'SUSPENDED', _("معلق شده")
        CANCELED = 'CANCELED', _("لغو شده")
        EXPORTING = 'EXPORTING', _("در حال صدور")
        IMPORTING = 'IMPORTING', _("در حال ورود")

    product = models.ManyToManyField(Product, related_name='production_orders', verbose_name=_("محصول"))
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='production_orders',
        verbose_name=_("پروژه مرتبط")
    )
    quantity = models.PositiveIntegerField(verbose_name=_("تعداد/مقدار"))
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        verbose_name=_("وضعیت")
    )
    assigned_to = models.ManyToManyField(
        Group,
        blank=True,
        related_name='production_tasks',
        verbose_name=_("مسئول انجام")
    )
    machine_used = models.ManyToManyField(
        Machine,
        blank=True,
        related_name='production_orders',
        verbose_name=_("دستگاه مورد استفاده")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("تاریخ ایجاد"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("تاریخ تکمیل"))

    class Meta:
        verbose_name = _("سفارش تولید/کار")
        verbose_name_plural = _("سفارشات تولید/کار")
        ordering = ['-created_at']

    def __str__(self):
        product_name = self.product.name if self.product else _("نامشخص")
        project_name = self.project.name if self.project else _("عمومی")
        return f"سفارش {product_name} به تعداد {self.quantity} برای پروژه {project_name}"


class InventoryItem(models.Model):
    """
    برای مدیریت موجودی دقیق هر محصول در مکان‌های مختلف و با وضعیت‌های گوناگون.
    """
    class ConditionChoices(models.TextChoices):
        AVAILABLE = 'AVAILABLE', _("موجود و سالم")
        RESERVED = 'RESERVED', _("رزرو شده")
        DAMAGED = 'DAMAGED', _("آسیب دیده")
        IN_TRANSIT = 'IN_TRANSIT', _("در حال انتقال")

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="inventory_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_items')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, related_name="inventory_items", null=True, blank=True)
    # شما می‌توانید یک مدل Location(انبار) هم بسازید و اینجا به آن ForeignKey بزنید
    # location = models.ForeignKey(Location, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name=_("تعداد موجودی"))
    condition = models.CharField(
        max_length=20,
        choices=ConditionChoices.choices,
        default=ConditionChoices.AVAILABLE,
        verbose_name=_("وضعیت کالا")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("تاریخ ایجاد"))
    last_updated = models.DateTimeField(auto_now=True, verbose_name=_("تاریخ آخرین بروزرسانی"))

    class Meta:
        verbose_name = _("موجودی انبار")
        verbose_name_plural = _("موجودی‌های انبار")
        # جلوگیری از ثبت رکورد تکراری برای یک محصول با یک وضعیت در یک مکان
        # unique_together = ('product', 'location', 'condition')

    def __str__(self):
        return f"{self.quantity} عدد از {self.product.name} ({self.get_condition_display()})"