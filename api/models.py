from django.db import models
from accounts.models import CustomUser
from django.utils import timezone
from decimal import Decimal


class BoardAdjustment(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='board_adjustments',
        verbose_name="کاربر مورد تنظیم"
    )
    year = models.IntegerField(
        verbose_name="سال شمسی تنظیم",
        null=True
    )
    month = models.IntegerField(
        verbose_name="ماه شمسی تنظیم",
        null=True
    )
    adjustment_value = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="مقدار تنظیم شده"
    )
    last_updated = models.DateTimeField(auto_now=True, verbose_name="آخرین به‌روزرسانی")
    last_adjusted_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='adjusted_users',
        verbose_name="تنظیم کننده"
    )

    class Meta:
        verbose_name = "تنظیم هیئت مدیره"
        verbose_name_plural = "تنظیمات هیئت مدیره"
        unique_together = ('user', 'year', 'month')

    def __str__(self):
        return f"تنظیم امتیاز برای {self.user.get_full_name()} در {self.year}/{self.month}: {self.adjustment_value}"
