import jdatetime
import pandas as pd
from accounts.models import CustomUser
from jdatetime import date as jdate
import pytz
from django.utils import timezone

iran_tz = pytz.timezone('Asia/Tehran')

def get_jalali_date():
    now_utc = timezone.now()
    now_iran = now_utc.astimezone(iran_tz)

    today = jdatetime.date.fromgregorian(date=now_iran.date())


    # today = jdatetime.date.today()
    today = tuple([today.year, today.month, today.day])
    return today
    # return today.year, today.month, today.day


def get_jalali_date_format():
    now_utc = timezone.now()
    now_iran = now_utc.astimezone(iran_tz)

    today = jdatetime.date.fromgregorian(date=now_iran.date())

    return today


def get_jalali_date_time():
    now_utc = timezone.now()
    # now_iran = now_utc.astimezone(iran_tz)

    now = jdatetime.datetime.fromgregorian(datetime=now_utc.now(tz=iran_tz))
    return now


def get_jalali_days_in_month(year, month):
    """
    Calculates the number of days in a given Jalali month and year.
    Uses the rules of the Jalali calendar and jdatetime.date.isleap() for leap year check.
    """
    if 1 <= month <= 6:
        return 31
    elif 7 <= month <= 11:
        return 30
    elif month == 12:
        # بررسی سال کبیسه برای ماه اسفند
        try:
            # استفاده از تابع isleap کتابخانه jdatetime برای تشخیص سال کبیسه
            if jdate.isleap(year): # <-- استفاده از jdate.isleap()
                return 30 # اسفند در سال کبیسه ۳۰ روز دارد
            else:
                return 29 # اسفند در سال عادی ۲۹ روز دارد
        except AttributeError:
            # اگر حتی jdate.isleap() هم مشکل داشت (که بعید است اما ممکن است)،
            # می توانیم یک تشخیص کبیسه دستی جایگزین کنیم، اما فعلاً فرض می کنیم isleap کار می کند.
            print(f"Warning: jdate.isleap({year}) failed. Cannot determine if {year} is leap year.")
            # در صورت خطا در تشخیص کبیسه، بر اساس شایع ترین حالت (سال عادی) ۲۹ روز برمی گردانیم.
            return 29 # بازگشت ۲۹ روز در صورت خطا (به عنوان یک fallback)

    else:
        # اگر شماره ماه نامعتبر باشد (نباید رخ دهد اگر ورودی درست باشد)
        raise ValueError(f"شماره ماه نامعتبر: {month}")


def generate_unique_username(first_name, last_name):
    base_username = f"{first_name}.{last_name}".replace(" ", "").lower()
    username = base_username
    counter = 1

    while CustomUser.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    return username


def create_users_from_excel():
    df = pd.read_excel("data/users.xlsx")

    for full_name in df["لیست کارکنان فعال"]:
        try:
            parts = full_name.strip().split()
            if len(parts) < 2:
                print(f"❌ نام ناقص: {full_name}")
                continue

            first_name = parts[0]
            last_name = ' '.join(parts[1:])

            username = generate_unique_username(first_name, last_name)

            # ایجاد کاربر
            user = CustomUser.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password="12345678qwer",  # رمز پیش‌فرض
                access_level=3,  # کارمند عادی
            )

            print(f"✅ ثبت شد: {user.get_full_name()} با نام کاربری {username}")

        except Exception as e:
            print(f"❌ خطا در ثبت {full_name}: {e}")
