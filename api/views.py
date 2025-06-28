import itertools

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.test.client import RequestFactory
from .permissions import IsBoardOfDirectors
from targets.models import Target
from accounts.models import MonthlyScore, DailyManagerScore, CustomUser
from .serializers import TargetSerN, MonthlyScoreSerN, DailyScoreSerN, UserMiniSerN
import datetime
from jdatetime import datetime as jdt_datetime
from decimal import Decimal, ROUND_DOWN
from openpyxl.utils import get_column_letter
from django.db.models import Count, Sum, F, Case, When, Value, DecimalField, Q
from django.db.models.functions import Cast, Coalesce
from openpyxl.utils import get_column_letter
import jdatetime
from . import utils
import pytz
from django.utils import timezone
from .models import BoardAdjustment  # مدل جدید را وارد کنید
from rest_framework import viewsets, status
from jdatetime import timedelta

try:
    iran_tz = pytz.timezone("Asia/Tehran")
except pytz.UnknownTimeZoneError:
    iran_tz = timezone.get_default_timezone()


def is_board_of_directors(user):
    return user.is_authenticated and hasattr(user, 'access_level') and user.access_level == -1


def get_response_from_monthly_score_viewset(request, year, month):
    factory = RequestFactory()
    internal_request = factory.get('/internal-api/monthlyscores/summary-by-access-level/')
    internal_request.user = request.user

    view = MonthlyScoreViewSetNew(year=year, month=month)
    view.request = internal_request
    view.action = 'summary_by_access_level'

    error_message = None
    try:
        response = view.summary_by_access_level(internal_request)
        if response.status_code == 200:
            summary_data = response.data

        else:
            summary_data = None
            error_message = f"خطا در دریافت داده از API: {response.status_code} {response.data.get('detail', '')}"
            print(error_message)

    except Exception as e:
        summary_data = None
        error_message = f"خطای غیرمنتظره: {e}"
        print(f"Error calling internal API: {e}")  # لاگ کردن خطا

    return summary_data, error_message


class MonthlyScoreViewSetNew(viewsets.ReadOnlyModelViewSet):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.year = kwargs["year"]
            self.month = kwargs["month"]
        except:
            pass

    # ... (queryset, serializer_class, permission_classes اصلی) ...

    # queryset = (
    #     MonthlyScore.objects
    #     .select_related("scorer", "target")
    #     .order_by("-year", "-month", "-id")
    # )
    # serializer_class = MonthlyScoreSerN
    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=['get'],
        url_path='summary-by-access-level',
        permission_classes=[IsBoardOfDirectors]  # فقط هیئت مدیره این خلاصه را می بیند
    )
    def summary_by_access_level(self, request):
        # ... (کدهای محاسبه تاریخ شمسی و میلادی ماه جاری) ...
        year = self.year
        month = self.month
        # year = int(request.GET.get("year", jdt_datetime.now().year))
        # month = int(request.GET.get("month", jdt_datetime.now().month))

        # محدوده اول و آخر ماه شمسی
        start_jdate = jdt_datetime(year, month, 1)
        end_jdate = start_jdate.replace(day=1).replace(month=month + 1 if month < 12 else 1,
                                                       year=year + 1 if month == 12 else year) - timedelta(days=1)

        start_gregorian = start_jdate.togregorian()
        end_gregorian = end_jdate.togregorian()

        # today_gregorian = datetime.date.today()
        # today_jalali = jdatetime.date.fromgregorian(date=today_gregorian)
        # jalali_year = today_jalali.year
        # jalali_month = today_jalali.month

        # jalali_start_date = jdatetime.date(jalali_year, jalali_month, 1)
        # from accounts.utils import get_jalali_days_in_month
        # days_in_jalali_month = get_jalali_days_in_month(jalali_year, jalali_month)
        # jalali_end_date = jdatetime.date(jalali_year, jalali_month, days_in_jalali_month)

        # gregorian_start_date = jalali_start_date.togregorian()
        # gregorian_end_date = jalali_end_date.togregorian()

        month_queryset = MonthlyScore.objects.filter(
            # فیلتر بر اساس تاریخ و scorer__isnull=False
            # timestamp__range=(gregorian_start_date, gregorian_end_date), # اگر timestamp فیلتر تاریخ است
            # یا اگر DailyManagerScore.date (jDateField) را برای خلاصه استفاده می کنید:
            # date__gte=jalali_start_date, date__lte=jalali_end_date, # اگر خلاصه ماهانه MonthlyScore بر اساس تاریخچه DailyScore است که اینطور نیست
            # فیلتر MonthlyScore معمولا بر اساس فیلدهای year و month است:
            target__access_level__in=[1, 2, 3],
            year=start_jdate.year, month=end_jdate.month,
            scorer__isnull=False
        )

        if not month_queryset:
            response_data = {
                'user_summaries': [],
                'overall_stats_by_access_level': list(zip([], [])),
                "no_score_givers_users": [],
                "jdate": [year, month]
            }

            return Response(response_data)

        # --- مرحله جدید: اضافه کردن فیلد coalesced_value به QuerySet ---
        # استفاده از Coalesce برای اطمینان از اینکه value هرگز NULL نیست قبل از هرگونه عملیات ریاضی
        queryset_with_coalesced_value = month_queryset.annotate(
            coalesced_value=Coalesce('value', Value(Decimal(0)), output_field=DecimalField())
        )

        # --- محاسبه تعداد کاربران برای هر سطح دسترسی (امتیازدهندگان) ---
        user_counts_by_level_qs = CustomUser.objects.filter(access_level__in=[1, 2, 3]) \
            .values('access_level') \
            .annotate(count=Count('id'))

        counts_access_level = {item['access_level']: item['count'] for item in user_counts_by_level_qs}

        access_level_counts = {i: counts_access_level.get(i, 0) for i in [1, 2, 3]}

        # TODO: You need to change Managers count
        access_level_counts[1] += 1

        access_level_counts_decimal = {
            level: Decimal(count)
            for level, count in access_level_counts.items()
        }
        # --- محاسبه امتیاز وزن‌دهی شده در سطح دیتابیس ---
        # حالا از فیلد 'coalesced_value' که می دانیم NULL نیست استفاده می کنیم
        weighted_value_annotation = Case(
            When(scorer__access_level__isnull=True, then=Value(Decimal(0))),
            # استفاده از access_level_counts_decimal که شامل تعداد Decimal است
            When(scorer__access_level=1,
                 then=F('coalesced_value') / Value(access_level_counts_decimal.get(1, Decimal(1)))),
            When(scorer__access_level=2,
                 then=F('coalesced_value') / Value(access_level_counts_decimal.get(2, Decimal(1)))),
            When(scorer__access_level=3,
                 then=F('coalesced_value') / Value(access_level_counts_decimal.get(3, Decimal(1)))),
            When(Q(scorer__access_level=-1) & Q(scorer_id=73), then=F('coalesced_value') / 8),
            # When(scorer__access_level=0, then=F('coalesced_value') / Value(access_level_counts_decimal.get(3, Decimal(1)))),
            # When(scorer__access_level=-1, then=F('coalesced_value') / Value(access_level_counts_decimal.get(3, Decimal(1)))),
            # default=F('coalesced_value'), # برای سایر سطوح دسترسی که ممکن است امتیاز دهند
            output_field=DecimalField()  # اطمینان از اینکه خروجی نهایی این Case Decimal است
        )

        # --- تجمع امتیازات وزن‌دهی شده برای هر کاربر هدف و نوع امتیاز ---
        score_aggregations = queryset_with_coalesced_value.values(
            'target__id',
            'target__first_name',
            'target__last_name',
            'target__username',
            'target__access_level',
            'score_type',
        ).annotate(
            total_score_for_type=Coalesce(Sum(weighted_value_annotation), Value(Decimal(0)))
        ).order_by(
            'target__access_level',
            'target__id',
            'score_type'
        )

        # --- مرحله جدید: واکشی امتیازات تنظیم شده هیئت مدیره ---
        # ایجاد دیکشنری برای دسترسی سریع به امتیاز تنظیم شده هر کاربر
        # از User IDs موجود در score_aggregations استفاده می کنیم
        # --- مرحله جدید: واکشی امتیازات تنظیم شده هیئت مدیره (تغییر یافته) ---
        user_ids_in_summary = [entry['target__id'] for entry in score_aggregations.values('target__id').distinct()]
        board_adjustments_qs = BoardAdjustment.objects.filter(
            user__id__in=user_ids_in_summary,
            year=year,  # اضافه کردن فیلتر سال
            month=month  # اضافه کردن فیلتر ماه
        ).values('user__id', 'adjustment_value')

        adjustment_dict = {item['user__id']: item['adjustment_value'] for item in board_adjustments_qs}

        # user_ids_in_summary = [entry['target__id'] for entry in score_aggregations.values('target__id').distinct()]
        # board_adjustments_qs = BoardAdjustment.objects.filter(
        #      user__id__in=user_ids_in_summary # فیلتر بر اساس کاربرانی که در خلاصه هستند
        # ).values('user__id', 'adjustment_value')

        adjustment_dict = {item['user__id']: item['adjustment_value'] for item in board_adjustments_qs}

        # --- تبدیل نتایج تجمع به فرمت مطلوب خلاصه کاربران ---
        summary_data = {}
        for entry in score_aggregations:
            user_id = entry['target__id']
            user_access_level = entry['target__access_level']
            score_type = entry['score_type']
            total_score_for_type = entry['total_score_for_type'] or Decimal(0)

            if user_id not in summary_data:
                # دریافت امتیاز تنظیم شده برای این کاربر
                adjustment = adjustment_dict.get(user_id, Decimal('0.000'))

                summary_data[user_id] = {
                    'user': {
                        'id': user_id,
                        'first_name': entry['target__first_name'],
                        'last_name': entry['target__last_name'],
                        'username': entry['target__username'],
                    },
                    'access_level': user_access_level,
                    'scores_by_type': {},
                    'total_monthly_score': Decimal(0),  # مجموع امتیاز محاسبه شده اصلی
                    'total_monthly_avg': Decimal(0),  # میانگین امتیاز محاسبه شده اصلی
                    'board_adjustment': adjustment,  # امتیاز تنظیم شده
                    # total_monthly_score_adjusted بعد از تکمیل total_monthly_score محاسبه می شود
                }

            # جمع کردن امتیازات بر اساس نوع
            summary_data[user_id]['scores_by_type'][str(score_type)] = total_score_for_type.quantize(Decimal('0.001'),
                                                                                                     rounding=ROUND_DOWN)
            summary_data[user_id]['total_monthly_score'] += total_score_for_type  # جمع کردن امتیاز محاسبه شده اصلی

        # محاسبه میانگین و مجموع نهایی تنظیم شده پس از تکمیل جمع امتیازات بر اساس نوع
        final_summary_list = []
        for user_id, user_data in summary_data.items():
            num_score_types = len(user_data['scores_by_type'])
            if num_score_types > 0:
                user_data['total_monthly_avg'] = (user_data['total_monthly_score'] / num_score_types).quantize(
                    Decimal('0.01'), rounding=ROUND_DOWN)
            else:
                user_data['total_monthly_avg'] = Decimal(0)

            # محاسبه مجموع نهایی امتیاز با تنظیم
            user_data['total_monthly_score_adjusted'] = (
                    user_data['total_monthly_score'] + user_data['board_adjustment']).quantize(Decimal('0.001'),
                                                                                               rounding=ROUND_DOWN)

            final_summary_list.append(user_data)

        # --- محاسبه آمار کلی بر اساس سطوح دسترسی ---
        # این بخش بر اساس مجموع امتیازات *وزن‌دهی شده اصلی* کاربران در هر سطح محاسبه می شود (همانند قبل)
        overall_stats = {}
        for level in [1, 2, 3]:
            level_name = (
                "مدیر میانی" if level == 1 else
                "کارمند برتر" if level == 2 else
                "کارمند عادی"
            )
            overall_stats[level] = {
                'level': level,
                'name': level_name,
                'count': access_level_counts_decimal.get(level, 0),
                'total_score_sum': Decimal(0),
            }

        for user_data in final_summary_list:
            level = user_data['access_level']
            overall_stats[level]['total_score_sum'] += user_data.get('total_monthly_score', Decimal(0))

        try:
            overall_stats[1]["sum"] = Decimal(sum([overall_stats[d]["total_score_sum"] for d in overall_stats]))
        except Exception as e:
            print(e)
            if not 1 in overall_stats:
                print("Amir Start")
                overall_stats[1] = {}
                overall_stats[1]["sum"] = Decimal(
                    sum([overall_stats[d]["total_score_sum"] if overall_stats[d] else 0 for d in overall_stats]))
                print("Amir end")

        # --- پیدا کردن کاربرانی که هیچ امتیازی در ماه نداده اند (همانند قبل) ---
        scorers_in_month_ids = month_queryset.values_list('scorer__id', flat=True).distinct()
        no_score_givers_users_count_list = []
        no_score_givers_users_list = []

        for i in [1, 2, 3]:  # مدیران و شاید کارمندان برتر
            users_who_gave_no_scores_qs = CustomUser.objects.filter(
                access_level=i
            ).exclude(
                id__in=scorers_in_month_ids
            )
            no_score_givers_users_list.append(list(users_who_gave_no_scores_qs))

            no_score_givers_count = users_who_gave_no_scores_qs.values('access_level').annotate(
                count=Count('id')
            ).order_by('access_level')

            no_score_givers_users_count_list.append(no_score_givers_count)

        # TODO: find 73 and do changes
        # # --- بررسی اینکه آیا کاربر 73 امتیازی داده یا نه ---
        if 73 not in scorers_in_month_ids:
            # اضافه‌کردن به لیست شمارش access_level=1
            added = False
            for group in no_score_givers_users_count_list:
                for item in group:
                    if item['access_level'] == 1:
                        item['count'] += 1
                        added = True
                        break
                if added:
                    break
            if not added:
                # اگر access_level=1 اصلاً وجود نداشت
                no_score_givers_users_count_list[0] = [{'access_level': 1, 'count': 1}]

            # اضافه‌کردن به لیست کاربران بدون امتیاز سطح 1
            user_73 = CustomUser.objects.filter(id=73).first()
            if user_73:
                no_score_givers_users_list[0].append(user_73)  # index 0 مربوط به سطح 1 هست


        # no_score_givers_users_list
        no_score_givers_users_list = itertools.chain.from_iterable(no_score_givers_users_list)

        # --- مرتب سازی لیست ها ---
        # مرتب سازی لیست خلاصه کاربران
        final_summary_list = sorted(
            final_summary_list,
            key=lambda x: x['total_monthly_score'],  # یا 'total_monthly_score_adjusted' اگر مرتب سازی بر اساس نهایی است
            reverse=True  # از بیشترین به کمترین
        )

        # مرتب سازی لیست آمار کلی سطوح دسترسی
        overall_stats_list = sorted(
            overall_stats.values(),
            key=lambda x: x['level']
        )

        # --- فرمت کردن خروجی نهایی ---
        response_data = {
            'user_summaries': final_summary_list,
            'overall_stats_by_access_level': list(zip(overall_stats_list, no_score_givers_users_count_list)),
            "no_score_givers_users": no_score_givers_users_list,
            "jdate": [year, month]
        }

        return Response(response_data)

    @action(
        detail=False,  # این اکشن روی یک عضو خاص از MonthlyScore نیست، روی کل مجموعه است
        methods=['post'],
        url_path='adjust-board-score',  # مسیر URL برای این اکشن
        permission_classes=[IsBoardOfDirectors]  # فقط هیئت مدیره اجازه تنظیم دارد
    )
    def adjust_board_score(self, request):
        user = request.user
        target_user_id = request.data.get('user_id')
        adjustment_delta = request.data.get('delta')
        # adjustment_year = self.year
        # adjustment_month = self.month

        adjustment_year = request.data.get('year')  # دریافت سال
        adjustment_month = request.data.get('month')  # دریافت ماه

        if not all([target_user_id, adjustment_delta is not None, adjustment_year, adjustment_month]):
            return Response(
                {"detail": "شناسه کاربر، مقدار تغییر، سال و ماه الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = CustomUser.objects.get(id=target_user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "کاربر مورد نظر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            adjustment_delta = Decimal(adjustment_delta)
            adjustment_year = int(adjustment_year)
            adjustment_month = int(adjustment_month)
        except (ValueError, TypeError):
            return Response(
                {"detail": "مقدار تغییر، سال یا ماه نامعتبر است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # پیدا کردن یا ایجاد رکورد تنظیم برای این کاربر در ماه و سال مشخص
        board_adjustment, created = BoardAdjustment.objects.get_or_create(
            user=target_user,
            year=adjustment_year,  # اضافه کردن سال به شرط get_or_create
            month=adjustment_month,  # اضافه کردن ماه به شرط get_or_create
            defaults={
                'adjustment_value': Decimal('0.000'),
                'last_adjusted_by': user,
                'last_updated': timezone.now()
            }
        )

        # اعمال تغییر در مقدار تنظیم شده
        board_adjustment.adjustment_value += adjustment_delta
        board_adjustment.last_adjusted_by = user
        board_adjustment.last_updated = timezone.now()
        board_adjustment.save()

        return Response(
            {
                "user_id": target_user_id,
                "year": adjustment_year,
                "month": adjustment_month,
                "new_adjustment_value": board_adjustment.adjustment_value.quantize(Decimal('0.000'),
                                                                                   rounding=ROUND_DOWN),
            },
            status=status.HTTP_200_OK
        )
    # def adjust_board_score(self, request):
    #     """تنظیم امتیاز یک کاربر توسط هیئت مدیره."""
    #     user = request.user # کاربری که درخواست را ارسال کرده (باید عضو هیئت مدیره باشد)
    #     target_user_id = request.data.get('user_id') # شناسه کاربری که قرار است امتیاز آن تنظیم شود
    #     adjustment_delta = request.data.get('delta') # مقدار تغییر (معمولا +1 یا -1)
    #
    #     if not target_user_id or adjustment_delta is None:
    #         return Response(
    #             {"detail": "شناسه کاربر و مقدار تغییر الزامی است."},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
    #
    #     try:
    #         target_user = CustomUser.objects.get(id=target_user_id)
    #     except CustomUser.DoesNotExist:
    #         return Response(
    #             {"detail": "کاربر مورد نظر یافت نشد."},
    #             status=status.HTTP_404_NOT_FOUND
    #         )
    #
    #     # اطمینان از اینکه delta یک عدد اعشاری است
    #     try:
    #         adjustment_delta = Decimal(adjustment_delta)
    #     except Exception:
    #          return Response(
    #              {"detail": "مقدار تغییر نامعتبر است."},
    #              status=status.HTTP_400_BAD_REQUEST
    #          )
    #
    #
    #     # پیدا کردن یا ایجاد رکورد تنظیم برای این کاربر
    #     # get_or_create یک تاپل برمی گرداند: (object, created)
    #     board_adjustment, created = BoardAdjustment.objects.get_or_create(
    #         user=target_user,
    #         defaults={
    #             'adjustment_value': Decimal('0.000'),
    #             'last_adjusted_by': user,
    #             'last_updated': timezone.now() # یا timezone.now().astimezone(iran_tz) بسته به نیاز
    #         }
    #     )
    #
    #     # اعمال تغییر در مقدار تنظیم شده
    #     board_adjustment.adjustment_value += adjustment_delta
    #     board_adjustment.last_adjusted_by = user
    #     board_adjustment.last_updated = timezone.now() # بروزرسانی زمان آخرین تغییر
    #     board_adjustment.save()
    #
    #     # برگرداندن مقدار تنظیم شده جدید (و شاید مجموع جدید)
    #     return Response(
    #         {
    #             "user_id": target_user_id,
    #             "new_adjustment_value": board_adjustment.adjustment_value.quantize(Decimal('0.000'), rounding=ROUND_DOWN),
    #             # برای محاسبه total_monthly_score_adjusted در اینجا، نیاز به مقدار total_monthly_score کاربر داریم
    #             # این مقدار در summary_by_access_level محاسبه می شود و در اینجا در دسترس نیست مگر اینکه مجدداً محاسبه شود
    #             # یا بهترین راه این است که فرانت اند پس از دریافت پاسخ موفقیت، خودش مجموع جدید را محاسبه کند
    #             # یا پس از موفقیت، کل لیست خلاصه ماهانه را مجدداً از API دریافت کند (ساده ترین راه).
    #             # فرض می کنیم فرانت اند پس از موفقیت، کل لیست را مجدداً دریافت می کند یا فقط ستون مربوطه را بروز می کند.
    #         },
    #         status=status.HTTP_200_OK
    #     )
    #


class TargetViewSetNew(viewsets.ReadOnlyModelViewSet):
    # ...
    queryset = Target.objects.select_related("user").order_by("-submission_date")
    serializer_class = TargetSerN
    permission_classes = [IsAuthenticated]  # یا IsAuthenticatedOrReadOnly

    @action(detail=False, methods=['get'])
    def counts(self, request):
        # ... (کد فعلی counts) ...
        target_counts = Target.objects.values(
            'user__id',
            'user__first_name',
            'user__last_name',
            'user__username'
        ).annotate(
            total_targets=Count('id')
        ).order_by('user__id')

        return Response(list(target_counts))


class DailyScoreViewSetNew(viewsets.ReadOnlyModelViewSet):
    # ...
    queryset = DailyManagerScore.objects.select_related("manager", "employee").order_by("-date", "-id")
    serializer_class = DailyScoreSerN
    permission_classes = [IsAuthenticated]  # یا IsAuthenticatedOrReadOnly

    @action(detail=False, methods=['get'], url_path='manager-totals')
    def manager_totals(self, request):
        # ... (کد فعلی manager_totals) ...
        manager_totals = DailyManagerScore.objects.values(
            'manager__id',
            'manager__first_name',
            'manager__last_name',
            'manager__username'
        ).annotate(
            total_score_given=Sum('value'),
            count_scores_given=Count('id')
        ).order_by('manager__id')

        return Response(list(manager_totals))


def monthly_scores_summary_excel(request):
    return utils.monthly_scores_summary_excel_func(request)


@user_passes_test(is_board_of_directors)
def monthly_scores_summary(request):
    try:
        year = int(request.GET.get("year", jdt_datetime.now().year))
        month = int(request.GET.get("month", jdt_datetime.now().month))
    except Exception as e:
        year = jdt_datetime.now().year
        month = jdt_datetime.now().month
        print(e)

    match request.GET.get("export"):
        case "excel":
            return monthly_scores_summary_excel(request)

    """
    Django view to display the monthly score summary page for the Board of Directors.
    Fetches data internally from the MonthlyScoreViewSetNew custom action.
    """

    summary_data, error_message = get_response_from_monthly_score_viewset(request=request, year=year, month=month)
    context = {
        'summary_data': summary_data,
        'error_message': error_message if 'error_message' in locals() else None  # پیام خطا اگر وجود داشته باشد
    }

    # Render the template
    return render(request, 'monthly_summary.html', context)
