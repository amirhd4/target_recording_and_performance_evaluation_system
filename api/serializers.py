# api/serializers.py  (نسخه‌ی مختصر و کامل)

from rest_framework import serializers
from accounts.models import CustomUser, MonthlyScore, DailyManagerScore
from targets.models  import Target

class UserMiniSerN(serializers.ModelSerializer):
    class Meta:
        model  = CustomUser
        fields = ("id", "first_name", "last_name", "username")


class TargetSerN(serializers.ModelSerializer):
    user = UserMiniSerN(read_only=True)      # ← کاربری که این هدف را ایجاد کرده

    class Meta:
        model  = Target
        fields = ("id", "user", "content", "submission_date")


class MonthlyScoreSerN(serializers.ModelSerializer):
    scorer = UserMiniSerN(read_only=True)
    # اصلاح: فیلد target در مدل MonthlyScore به CustomUser اشاره می‌کند، پس باید از UserMiniSer استفاده شود
    target = UserMiniSerN(read_only=True) # <-- از UserMiniSer استفاده کنید، نه TargetSer

    class Meta:
        model  = MonthlyScore
        fields = (
            "id", "scorer", "target", # حالا scorer و target هر دو با UserMiniSer سریالایز می‌شوند
            "score_type", "value", "year", "month",
        )


class DailyScoreSerN(serializers.ModelSerializer):
    manager  = UserMiniSerN(read_only=True)
    employee = UserMiniSerN(read_only=True)

    class Meta:
        model  = DailyManagerScore
        fields = ("id", "manager", "employee", "value", "date")

