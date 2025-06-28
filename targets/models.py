from django.db import models
from accounts.models import CustomUser
from jdatetime import date as jdate
from jdatetime import datetime as jdatetime
from django_jalali.db import models as jmodels
from accounts.utils.sanitize import SanitizedModelMixin
from django.contrib.auth.models import Group

class Target(SanitizedModelMixin, models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='targets')
    content = models.TextField(verbose_name="متن هدف")
    submission_date = models.DateTimeField(verbose_name="تاریخ ثبت")
    created_at_jalali = jmodels.jDateTimeField(
        auto_now_add=True,
        null = True,
        verbose_name="تاریخ و زمان ایجاد",
    )
    updated_at_jalali = jmodels.jDateTimeField(
        auto_now=True,
        null=True,
        verbose_name="تاریخ و زمان بروزرسانی"
    )

    def save(self, *args, **kwargs):
        from accounts.utils.sanitize import strip_html
        self.content_plain = strip_html(self.content)
        super().save(*args, **kwargs)


    class Meta:
        # unique_together = ('user', 'submission_date')
        verbose_name = "هدف"
        verbose_name_plural = "اهداف"
    
    # def __str__(self):
    #     try:
    #         jalali_date_str = jdatetime.fromgregorian(datetime=self.submission_date).strftime("%Y/%m/%d - %H:%M:%S")
    #     except AttributeError:
    #         jalali_date_str = str(self.submission_date)

    #     return f"هدف برای {self.user.get_full_name()} در تاریخ {jalali_date_str}"



# --- مدل جدید برای انواع وظایف ---
class TaskType(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='task_types',
        verbose_name="گروه کاربری"
    )
    title = models.CharField(max_length=100, verbose_name="عنوان وظیفه/محصول")
    unit = models.CharField(max_length=30, blank=True, null=True, verbose_name="واحد", help_text="مثال: عدد، کیلوگرم، متر")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    is_active = models.BooleanField(default=True, verbose_name="فعال باشد؟")
    DATA_TYPE_CHOICES = (
        ("text", "متن"),
        ("number", "عدد"),
    )
    data_type = models.CharField(choices=DATA_TYPE_CHOICES, default=1, verbose_name="نوع داده")

    class Meta:
        verbose_name = "نوع محصول/وظیفه"
        verbose_name_plural = "انواع وظایف"
        ordering = ['order'] # وظایف بر اساس فیلد order مرتب می‌شوند

    def __str__(self):
        return f"{self.title} ({self.group.name})"