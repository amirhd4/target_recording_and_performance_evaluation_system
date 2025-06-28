from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django_jalali.db import models as jmodels
import os
from accounts.utils.sanitize import SanitizedModelMixin
from django.db.models import Q


class CustomUser(AbstractUser):
    LEVEL_CHOICES = (
        (-1, "هیئت مدیره"),
        (0, "مدیر عامل"),
        (1, "مدیر میانی"),
        (2, "سرپرست"),
        (3, "کارمند برتر"),
        (4, "کارمند عادی"),
    )
    SEX_CHOICES = (
        (2, "نامشخص"),
        (0, "مرد"),
        (1, "زن")
    )

    access_level = models.SmallIntegerField(choices=LEVEL_CHOICES, default=3)
    supervisor = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates')
    sex = models.PositiveSmallIntegerField(default=0, null=True, blank=True, help_text="جنسیت", choices=SEX_CHOICES)

    def __str__(self):
        return self.get_full_name()


class UserResponsibility(models.Model):
    """مدلی برای ذخیره انواع شرح وظایف برای هر کاربر."""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE, # اگر کاربر حذف شود، شرح وظایف مرتبط هم حذف شوند
        related_name='responsibilities', # نامی که با آن از شیء کاربر به وظایف دسترسی پیدا می کنید (مثال: user.responsibilities.all())
        verbose_name="کاربر مورد نظر"
    )
    responsibility_type = models.CharField(
        max_length=100, # حداکثر طول برای عنوان یا نوع وظیفه (مثال: "وظایف عمومی", "مسئولیت های پروژه X")
        verbose_name="نوع وظیفه / عنوان"
    )
    description = models.TextField(
        verbose_name="شرح کامل وظیفه" # فیلد متنی برای توضیحات طولانی
    )
    # فیلد اختیاری برای مرتب سازی دستی در صورت نیاز
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ترتیب نمایش"
    )

    class Meta:
        verbose_name = "شرح وظیفه کاربر"
        verbose_name_plural = "شرح وظایف کاربران"
        # مرتب سازی پیش فرض: اول بر اساس کاربر، بعد بر اساس ترتیب، بعد نوع وظیفه
        ordering = ['user__id', 'order', 'responsibility_type']
        # اضافه کردن محدودیت منحصر به فرد بودن اختیاری است، اگر نمی خواهید یک نوع وظیفه دوبار برای یک کاربر ثبت شود:
        # unique_together = ('user', 'responsibility_type')


    def __str__(self):
        # نمایش نام کاربر و نوع وظیفه برای شناسایی بهتر در پنل ادمین و کنسول
        try:
            user_full_name = self.user.get_full_name() or self.user.username # نام کامل یا نام کاربری
        except CustomUser.DoesNotExist:
            user_full_name = "کاربر نامشخص"
        return f"{user_full_name} - {self.responsibility_type}"


class RegulationDocument(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان آیین‌نامه")
    file = models.FileField(upload_to='regulations/', verbose_name="فایل PDF")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات کوتاه")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ بارگذاری")
    is_active = models.BooleanField(default=True, verbose_name="فعال برای نمایش به کاربران")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "آیین‌نامه"
        verbose_name_plural = "آیین‌نامه‌ها و دستورالعمل‌ها"
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


class UserRegulationAcknowledgement(models.Model):
    user = models.ForeignKey(
        CustomUser, # یا settings.AUTH_USER_MODEL
        on_delete=models.CASCADE,
        related_name='regulation_acknowledgements',
        verbose_name="کاربر"
    )
    regulation = models.ForeignKey(
        RegulationDocument,
        on_delete=models.CASCADE,
        related_name='user_acknowledgements',
        verbose_name="آیین‌نامه"
    )
    is_read = models.BooleanField(default=False, verbose_name="مطالعه شده")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ مطالعه")

    class Meta:
        unique_together = ('user', 'regulation') # هر کاربر برای هر آیین‌نامه فقط یک رکورد خواهد داشت
        verbose_name = "تاییدیه مطالعه آیین‌نامه"
        verbose_name_plural = "تاییدیه های مطالعه آیین‌نامه‌ها توسط کاربران"
        ordering = ['user', 'regulation__order']

    def __str__(self):
        return f"{self.user} - {self.regulation.title} (خوانده شده: {self.is_read})"


class UserOverallRegulationAcknowledgement(models.Model):
    user = models.OneToOneField( # هر کاربر فقط یک رکورد تاییدیه کلی دارد
        CustomUser, # یا settings.AUTH_USER_MODEL
        on_delete=models.CASCADE,
        related_name='overall_regulation_acknowledgement',
        verbose_name="کاربر"
    )
    all_regulations_confirmed = models.BooleanField(default=False, verbose_name="تایید مطالعه همه آیین‌نامه‌ها")
    confirmation_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید نهایی")
    # می‌توانید یک فیلد برای ذخیره لیست ID آیین‌نامه‌های تایید شده در آن لحظه اضافه کنید اگر نیاز به تاریخچه دقیق‌تری دارید
    # confirmed_regulations_snapshot = models.JSONField(null=True, blank=True, verbose_name="لیست آیین‌نامه‌های تایید شده")


    class Meta:
        verbose_name = "تاییدیه کلی مطالعه آیین‌نامه‌ها"
        verbose_name_plural = "تاییدیه های کلی مطالعه آیین‌نامه‌ها توسط کاربران"

    def __str__(self):
        return f"تاییدیه کلی کاربر: {self.user} (تایید شده: {self.all_regulations_confirmed})"


# @deconstructible
def user_knowledge_management_upload_path(instance, filename):
    user_folder_name = f'user_{instance.user.id}'

    base_folder = 'knowledge_management_files'

    return os.path.join(base_folder, user_folder_name, filename)


class UserKnowledgeManagement(SanitizedModelMixin, models.Model):
    """مدلی برای ذخیره هر مورد از لیست مدیریت دانش برای یک کاربر."""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='knowledge_management',
        verbose_name="کاربر"
    )
    content = models.TextField(
        verbose_name="محتوای مدیریت دانش"
    )
    file_upload = models.FileField(
        upload_to=user_knowledge_management_upload_path,
        null=True,
        blank=True,
        verbose_name="فایل ضمیمه"
    )
    created_at_jalali = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ و ساعت ثبت"
    )
    # فیلد اختیاری برای ترتیب نمایش اگر نیاز باشد (مثلاً نمایش با ترتیب خاصی غیر از تاریخ ثبت)
    # order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")


    class Meta:
        verbose_name = "مورد مدیریت دانش کاربر"
        verbose_name_plural = "موارد مدیریت دانش کاربران"
        # مرتب سازی پیش فرض: بر اساس تاریخ ثبت، نزولی (جدیدترین مورد اول)
        ordering = ['-created_at_jalali']
        # اگر فیلد order را اضافه کردید، می توانید آن را در اینجا هم اضافه کنید:
        # ordering = ['user__id', 'order', '-created_at_jalali']

    def __str__(self):
        # نمایش بخشی از محتوا و نام کاربر برای شناسایی
        try:
            user_full_name = self.user.get_full_name() or self.user.username
        except CustomUser.DoesNotExist:
             user_full_name = "کاربر نامشخص"
        # نمایش 50 کاراکتر اول محتوا یا یک پیام پیش فرض
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{user_full_name} - {content_preview} ({self.created_at_jalali.strftime('%Y/%m/%d %H:%M')})"

    def save(self, *args, **kwargs):
        from accounts.utils.sanitize import strip_html
        self.content_plain = strip_html(self.content)
        super().save(*args, **kwargs)


class MonthlyScoreManager(models.Manager):
    def get_queryset(self):
        not_allowed_ids = []

        # فیلترهای مورد نظر: scorer غیرفعال، scorer با ID غیرمجاز، scorer با date_joined جدیدتر از jnow_limit
        return super().get_queryset().exclude(
            Q(scorer__is_active=False) |
            Q(target__is_active=False) |
            Q(scorer__id__in=not_allowed_ids) |
            Q(target__id__in=not_allowed_ids)
        )

class MonthlyScore(models.Model):
    SCORE_TYPE_CHOICES = (
        (1, "تحقق اهداف"),
        (2, "مسئولیت‌ها"),
        (3, "مدیریت دانش"),
    )

    objects = MonthlyScoreManager()

    scorer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='monthly_given_scores')
    target = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='monthly_received_scores')
    score_type = models.PositiveSmallIntegerField(choices=SCORE_TYPE_CHOICES)
    value = models.DecimalField(decimal_places=3, max_digits=6)
    year = models.IntegerField()
    month = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('scorer', 'target', 'score_type', 'year', 'month')

    def __str__(self):
        return f"{self.scorer} -> {self.target} ({self.get_score_type_display()}): {self.value}"

class DailyManagerScoreManager(models.Manager):
    def get_queryset(self):
        not_allowed_ids = []

        # فیلترهای مورد نظر: scorer غیرفعال، scorer با ID غیرمجاز، scorer با date_joined جدیدتر از jnow_limit
        return super().get_queryset().exclude(
            Q(manager__is_active=False) |
            Q(manager__is_active=False) |
            Q(employee__id__in=not_allowed_ids) |
            Q(employee__id__in=not_allowed_ids)
        )

class DailyManagerScore(models.Model):

    objects = DailyManagerScoreManager()

    manager = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='daily_scores_given')
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='daily_scores_received')
    date = jmodels.jDateField(default=timezone.now)
    value = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # TODO: Change here to best security
        # unique_together = ('manager', 'employee', 'date')
        pass

    def __str__(self):
        return f"{self.manager} to {self.employee} on {self.date}: {self.value}"
