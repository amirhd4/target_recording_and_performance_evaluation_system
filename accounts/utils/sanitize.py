import bleach
from django.db import models
from django.utils.html import strip_tags


class SanitizedModelMixin(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # فیلدهای متنی (TextField, CharField) رو پیدا کن و sanitize کن
        for field in self._meta.get_fields():
            if isinstance(field, (models.TextField, models.CharField)):
                val = getattr(self, field.name, None)
                if val:
                    cleaned = strip_html(val)
                    setattr(self, field.name, cleaned)
        super().save(*args, **kwargs)


# تگ‌های مجاز برای HTML تمیز شده
DEFAULT_ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3']

def sanitize_html(html: str, allowed_tags=None) -> str:
    """
    پاک‌سازی HTML از تگ‌های خطرناک. فقط تگ‌های مجاز باقی می‌مانند.
    """
    if allowed_tags is None:
        allowed_tags = DEFAULT_ALLOWED_TAGS
    return bleach.clean(html, tags=allowed_tags)

def strip_html(html: str) -> str:
    """
    حذف کامل تمام تگ‌های HTML، فقط متن خام باقی می‌ماند.
    """
    return strip_tags(html)

def sanitize_plain_text(text: str) -> str:
    """
    حذف تگ‌ها و کاراکترهای ناامن در ورودی فقط متنی (برای فرم‌های ساده).
    """
    text = strip_tags(text)
    return bleach.clean(text, tags=[], strip=True)
