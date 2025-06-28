from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.core.exceptions import ValidationError
from .models import MonthlyScore, DailyManagerScore, UserKnowledgeManagement
from django.contrib.auth.forms import PasswordChangeForm
import os

class KnowledgeManagementForm(forms.ModelForm):
    """
    ModelForm برای افزودن/ویرایش یک مورد مدیریت دانش (با استفاده از مدل UserKnowledgeManagement).
    """
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 60, 'placeholder': 'محتوای مورد مدیریت دانش را وارد کنید...'}),
        label="محتوا",
        required=True
    )
     # Define allowed extensions and max size
    ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'zip', 'rar', "xls", "xlsx"] # Add/remove as needed
    MAX_FILE_SIZE = 200 * 1024 * 1024

    file_upload = forms.FileField(
        label="فایل ضمیمه (حداکثر 200 مگابایت، فرمت‌های مجاز: {})".format(", ".join(ALLOWED_EXTENSIONS)),
        required=False # File upload is optional
    )
    # اگر فیلد order هم در مدل UserKnowledgeManagement دارید و می خواهید در فرم باشد:
    # order = forms.IntegerField(label="ترتیب نمایش", required=False, initial=0)

    class Meta:
        model = UserKnowledgeManagement # <--- مدل صحیح
        # فقط فیلدهای content و order (اگر اضافه کردید) را در فرم قرار می دهیم.
        fields = ['content', "file_upload"] # اگر order را اضافه کردید: ['content', 'order']

    def clean_file_upload(self):
        file = self.cleaned_data.get('file_upload')

        if file: # Only validate if a file was uploaded
            # Validate file size
            if file.size > self.MAX_FILE_SIZE:
                raise ValidationError(f"حجم فایل ضمیمه نباید بیشتر از 200 مگابایت باشد.")

            # Validate file extension
            filename = file.name
            extension = os.path.splitext(filename)[1].lower().lstrip('.') # Get extension, lowercase, remove leading dot
            if extension not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    "فرمت فایل ضمیمه مجاز نیست. فرمت‌های مجاز: {}.".format(", ".join(self.ALLOWED_EXTENSIONS))
                )

        return file # Return the cleaned file (or None if not uploaded)


class MonthlyScoreForm(forms.ModelForm):
    class Meta:
        model = MonthlyScore
        fields = ['target', 'score_type', 'value']


class DailyManagerScoreForm(forms.ModelForm):
    class Meta:
        model = DailyManagerScore
        fields = ['employee', 'value']


class PersianPasswordChangeForm(PasswordChangeForm):
    # متد __init__ فرم را بازنویسی می‌کنیم
    def __init__(self, *args, **kwargs):
        # فراخوانی متد __init__ کلاس پدر (PasswordChangeForm)
        super().__init__(*args, **kwargs)

        # **تنظیم دستی برچسب فیلدها به فارسی**
        self.fields['old_password'].label = "رمز عبور فعلی"
        self.fields['new_password1'].label = "رمز عبور جدید"
        self.fields['new_password2'].label = "تکرار رمز عبور جدید"

        # اگر نیاز به تغییر متن راهنمای فیلدها (help_text) هم دارید، اینجا می توانید تنظیم کنید
        # self.fields['new_password1'].help_text = "راهنمای فارسی برای رمز عبور جدید شما."
        # self.fields['new_password2'].help_text = "رمز عبور جدید خود را دوباره وارد کنید."