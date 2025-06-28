from collections import defaultdict
from datetime import datetime as python_datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Sum, Q
import json
from .utils.utils import get_jalali_date, get_jalali_days_in_month, get_jalali_date_time, iran_tz
from .models import CustomUser, MonthlyScore, DailyManagerScore, UserKnowledgeManagement, UserResponsibility, \
    RegulationDocument, UserRegulationAcknowledgement, UserOverallRegulationAcknowledgement
from targets.models import Target
import jdatetime
from jdatetime import datetime as jdt_datetime
import pytz
from django.utils import timezone
from .forms import KnowledgeManagementForm
import logging
from datetime import timedelta
from django.views.decorators.http import require_POST, require_GET
from django.utils.safestring import mark_safe
from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse
import openpyxl
from django.contrib.auth.decorators import user_passes_test
import os
from django.conf import settings
import itertools
from django.http import FileResponse, Http404


jalali_now = get_jalali_date_time().replace(day=1)
jnow = jalali_now - timedelta(days=6)
not_allowed_ids = [68]


# تابع کمکی برای پیدا کردن کاربرانی که شخص فعلی می‌تواند به آنها امتیاز دهد
def get_scoreable_users(user):
    """
    این تابع بر اساس قوانین جدید، لیست کاربرانی که کاربر فعلی (user)
    می‌تواند به آنها امتیاز روزانه بدهد را برمی‌گرداند.
    """
    scoreable_users_qs = CustomUser.objects.none()

    # قانون ۱: هیئت مدیره (سطح -۱) به مدیرعامل (سطح ۰) و مدیران میانی (سطح ۱) امتیاز می‌دهد
    if user.access_level == -1:
        scoreable_users_qs = CustomUser.objects.filter(access_level__in=[0, 1])

    # قانون ۲: مدیرعامل (سطح ۰) به مدیران میانی (سطح ۱) و سرپرستان (سطح ۲) امتیاز می‌دهد
    elif user.access_level == 0:
        scoreable_users_qs = CustomUser.objects.filter(access_level__in=[1, 2])

    # قانون ۳: مدیران میانی (سطح ۱) و سرپرستان (سطح ۲) به زیرمجموعه‌های مستقیم خود امتیاز می‌دهند
    elif user.access_level in [1, 2]:
        if user.subordinates.exists():
            scoreable_users_qs = user.subordinates.all()

    # اعمال فیلترهای عمومی
    final_users = scoreable_users_qs.filter(is_active=True).exclude(id=user.id)

    # --- اعمال استثناها ---
    # استثنای عمومی: کاربر با آیدی ۶۸ توسط هیچکس (به جز آیدی ۷۳) امتیاز نمی‌گیرد
    # if user.id != 73:
    final_users = final_users.exclude(id=68)
    # استثنای خاص: کاربر با آیدی ۷۳ می‌تواند به کاربر با آیدی ۶۸ امتیاز دهد
    if user.id == 73:
        user_68_qs = CustomUser.objects.filter(id=68, is_active=True)

        if user_68_qs.exists():
            user_68 = user_68_qs.first()
            new_list = CustomUser.objects.filter(
                # Q(id=user_68.id) | Q(id__in=user_68.subordinates.values_list('id', flat=True))
                id__in=user_68.subordinates.exclude(is_active=False).values_list('id', flat=True),
            )
            final_users = new_list | final_users


    return final_users.order_by('first_name', 'last_name')


@login_required
def dashboard_view(request):
    user = request.user
    today_jalali_parts = get_jalali_date()  # (year, month, day)
    current_year, current_month, current_day = today_jalali_parts
    num_days_in_current_month = get_jalali_days_in_month(current_year, current_month)

    # --- بخش امتیاز ماهانه  ---
    exclude_ids = itertools.chain.from_iterable([[0] if user.access_level == 1 else [user.id], not_allowed_ids])


    # if jnow > jdt_datetime.fromgregorian(datetime=request.user.date_joined).astimezone(iran_tz):
    #     all_other_users = list(CustomUser.objects.filter(access_level__gt=0).exclude(Q(id__in=exclude_ids) | Q(is_active=False)).order_by('first_name', 'last_name'))
    #     new_list = []
    #     for i in all_other_users:
    #         jsub = jdt_datetime.fromgregorian(datetime=i.date_joined).astimezone(iran_tz)
    #         if  jsub < jnow:
    #             new_list.append(i)
    #
    #     all_other_users = new_list
    #
    # else:
    #     all_other_users = []
    all_other_users = []
    all_other_users_monthly = []
    score_dict_from_db = {}
    existing_scores_by_user_map = {}
    monthly_scores_finalized = True

    # eligible_monthly_score_types_count = 0
    # if user.access_level in [1, 0, -1]: eligible_monthly_score_types_count = 3
    # elif user.access_level == 2: eligible_monthly_score_types_count = 2
    # elif user.access_level == 3: eligible_monthly_score_types_count = 1
    #
    # num_targets_for_monthly_score = len(all_other_users)
    # total_required_monthly_scores = num_targets_for_monthly_score * eligible_monthly_score_types_count
    # monthly_scores_qs = MonthlyScore.objects.filter(scorer=user, year=current_year, month=current_month).exclude(target__is_active=False)
    # submitted_monthly_scores_count = monthly_scores_qs.count()
    # monthly_scores_finalized = submitted_monthly_scores_count > 0 and submitted_monthly_scores_count == total_required_monthly_scores
    #
    # score_dict_from_db = {(score.target_id, score.score_type): score.value for score in monthly_scores_qs}
    # existing_scores_by_user_map = {}
    # for score in monthly_scores_qs:
    #     existing_scores_by_user_map.setdefault(score.target_id, set()).add(score.score_type)

    # --- بخش امتیاز روزانه (بازنویسی شده با منطق جدید) ---
    scoreable_users_today = get_scoreable_users(user)
    subordinates_for_template = []
    today_daily_scores_for_template = {}

    today_gregorian_date_for_filter = jdatetime.date.today().togregorian()

    if scoreable_users_today.exists():
        # دریافت اهداف امروز همه کاربران مجاز با یک کوئری
        targets_today = Target.objects.filter(
            submission_date__date=today_gregorian_date_for_filter,
            user__in=scoreable_users_today
        ).values('user_id', 'content')
        map_targets_today = {t['user_id']: t['content'] for t in targets_today}

        # دریافت امتیازات ثبت‌شده امروز با یک کوئری
        scored_today = DailyManagerScore.objects.filter(
            manager=user,
            employee__in=scoreable_users_today,
            date=today_gregorian_date_for_filter
        )
        today_daily_scores_for_template = {score.employee_id: score.value for score in scored_today}

        # آماده‌سازی لیست برای ارسال به تمپلیت
        for target_user in scoreable_users_today:
            subordinates_for_template.append({
                "subordinate": target_user,
                "target": {"content": map_targets_today.get(target_user.id)}
            })

    # --- بخش شناسایی فرصت‌های امتیازدهی روزهای گذشته (با منطق جدید) ---
    missed_daily_scores_opportunities = []
    subordinates_to_check_for_missed = get_scoreable_users(user)  # استفاده از همان منطق

    if subordinates_to_check_for_missed.exists():
        jdate = jdatetime.date.today()
        # فقط روزهای گذشته در ماه جاری شمسی را بررسی کن

        # TODO: Change here
        if jdate.day != 135:

            year = jdate.year
            month = jdate.month - 1
            day = jdate.day

            if month < 1:
                month = 12
                year -= 1


            first_day_of_prev_month = jdatetime.date(year, month, 1)
            # ساخت لیست روزها از اول ماه قبل تا امروز (inclusive)
            all_days = []
            current = first_day_of_prev_month

            while current <= jdate:
                all_days.append(current)
                current += timedelta(days=1)

            # past_days_jalali = [today_jalali_obj - timedelta(days=i) for i in range(1, today_jalali_obj.day)]
            past_days_jalali = all_days
            past_days_gregorian = [d.togregorian() for d in past_days_jalali]

            if past_days_gregorian:
                # دریافت تمام اهداف کاربران مورد نظر در روزهای گذشته با یک کوئری
                past_targets_qs = Target.objects.filter(
                    user__in=subordinates_to_check_for_missed,
                    submission_date__date__in=past_days_gregorian
                ).values('user_id', 'submission_date__date', 'content')
                targets_map = {(t['user_id'], t['submission_date__date']): t['content'] for t in past_targets_qs}

                # دریافت تمام امتیازات ثبت‌شده توسط مدیر در روزهای گذشته با یک کوئری
                existing_scores_qs = DailyManagerScore.objects.filter(
                    manager=user,
                    employee__in=subordinates_to_check_for_missed,
                    date__in=past_days_gregorian
                ).values('employee_id', 'date')
                existing_scores_set = {(s['employee_id'], s['date']) for s in existing_scores_qs}

                # پیدا کردن فرصت‌های از دست رفته
                for sub_obj in subordinates_to_check_for_missed:
                    for j_day in past_days_jalali:
                        g_day = j_day.togregorian()

                        target_content = targets_map.get((sub_obj.id, g_day))
                        score_exists = (sub_obj.id, g_day) in existing_scores_set

                        if target_content and not score_exists:
                            missed_daily_scores_opportunities.append({
                                'subordinate_name': f"{sub_obj.first_name} {sub_obj.last_name}",
                                'employee_id': sub_obj.id,
                                'jalali_date_str': j_day.strftime('%Y/%m/%d'),
                                'gregorian_date_to_submit': g_day.strftime('%Y-%m-%d'),
                                'target_content': target_content
                            })

    should_show_missed_scores_section = bool(missed_daily_scores_opportunities)

    # --- بخش اهداف و امتیازات خود کاربر (بازیابی دقیق کد اصلی شما) ---
    my_scores_targets_for_template = [] # نامی که تمپلت شما انتظار دارد
    monthly_targets_count_for_template = 0
    my_sum_scores_for_template = 0

    # Show user's own targets/scores only if they are not CEO/Board
    if not (user.access_level in [0, -1]):
        new_list_for_my_targets = []
        my_scores_processed_for_my_targets = []
        try:
            start_of_month_jalali = jdatetime.date(current_year, current_month, 1)

            if num_days_in_current_month is not None:
                end_of_month_jalali = jdatetime.date(current_year, current_month, num_days_in_current_month)
                start_gregorian_iso = start_of_month_jalali.togregorian().strftime('%Y-%m-%d')
                end_gregorian_iso = end_of_month_jalali.togregorian().strftime('%Y-%m-%d')

                # اهداف کاربر در ماه جاری
                user_monthly_targets_qs = Target.objects.filter(
                    user=user,
                    submission_date__date__gte=start_gregorian_iso,
                    submission_date__date__lte=end_gregorian_iso
                ).order_by('submission_date').exclude(user__is_active=False)
                monthly_targets_count_for_template = user_monthly_targets_qs.count()

                # امتیازات دریافت شده توسط کاربر در ماه جاری
                user_received_scores_qs = DailyManagerScore.objects.filter(
                    employee=user,
                    date__gte=start_gregorian_iso, # Assuming DailyManagerScore.date is stored in a way comparable to ISO string or Gregorian date
                    date__lte=end_gregorian_iso # Assuming DailyManagerScore.date is stored in a way comparable to ISO string or Gregorian date
                ).values('date', 'value', 'created_at') # .date() روی submission_date هدف است

                # If DailyManagerScore.date is jmodels.jDateField, you might need to adjust the filter
                # Example: If date is stored as jdatetime.date object:
                # user_received_scores_qs = DailyManagerScore.objects.filter(
                #     employee=user,
                #     date__gte=start_of_month_jalali,
                #     date__lte=end_of_month_jalali
                # ).values('date', 'value', 'created_at')

                # Need to ensure the key for user_scores_map matches the target_item.submission_date.date() type
                user_scores_map = {}
                for score in user_received_scores_qs:
                    # If DailyManagerScore.date is jmodels.jDateField, score['date'] is jdatetime.date
                    # If Target.submission_date is DateTimeField, target_item.submission_date.date() is datetime.date
                    # Need to ensure comparison is between the same types (both Gregorian datetime.date)
                    score_date_gregorian = score['date'].togregorian() if isinstance(score['date'], jdatetime.date) else score['date']
                    user_scores_map[score_date_gregorian] = score


                for target_item in user_monthly_targets_qs:
                    # تبدیل submission_date هدف به jdatetime با timezone
                    # Target.submission_date یک DateTimeField است (فرض بر این است)
                    target_submission_dt_iran = jdatetime.datetime.fromgregorian(datetime=target_item.submission_date).astimezone(iran_tz)
                    new_list_for_my_targets.append({
                        "submission_date": target_submission_dt_iran, # برای نمایش در تمپلت (jdatetime با تایم‌زون)
                        "content": target_item.content
                    })

                    # مقایسه با بخش تاریخ از submission_date هدف
                    # DailyManagerScore.date یک DateField یا jmodels.jDateField است
                    target_date_gregorian = target_item.submission_date.date() # این datetime.date خواهد بود

                    score_info = user_scores_map.get(target_date_gregorian)
                    processed_score_item = None
                    if score_info:
                        my_sum_scores_for_template += score_info["value"]
                        # DailyManagerScore.created_at یک DateTimeField است
                        score_created_at_iran = jdatetime.datetime.fromgregorian(datetime=score_info["created_at"]).astimezone(iran_tz)
                        processed_score_item = {
                            "value": score_info["value"],
                            "created_at": score_created_at_iran # برای نمایش در تمپلت (jdatetime با تایم‌زون)
                        }
                    my_scores_processed_for_my_targets.append(processed_score_item)

                # معکوس کردن برای نمایش از جدید به قدیم، مطابق کد شما
                new_list_for_my_targets.reverse()
                my_scores_processed_for_my_targets.reverse()
                my_scores_targets_for_template = zip(new_list_for_my_targets, my_scores_processed_for_my_targets)

        except ValueError as e_val_user:
            print(f"Invalid Jalali date ({current_year}/{current_month}) for user's targets: {e_val_user}")
        except Exception as e_gen_user:
            print(f"Error fetching user's monthly targets/scores: {e_gen_user}")
            # در صورت خطا، متغیرها مقادیر اولیه خود را حفظ می‌کنند (لیست خالی، تعداد و مجموع صفر)

    # +++ بخش شناسایی فرصت‌های امتیازدهی روزهای گذشته (با دستورات عیب‌یابی دقیق‌تر) +++
    #
    # missed_daily_scores_opportunities = []
    # subordinates_to_check_for_missed = CustomUser.objects.none() # Initialize as empty queryset
    #
    # # Determine which employees the current user can score for past days
    # if user.access_level in [0, -1]: # مدیرعامل یا هیئت مدیره
    #     # Can score all users with access_level > 0, excluding user 68 and themselves
    #     subordinates_to_check_for_missed = CustomUser.objects.filter(access_level__gt=0).exclude(Q(id__in=[user.id] + not_allowed_ids) | Q(is_active=False)).order_by('first_name', 'last_name')
    #
    # elif user.access_level in [1, 2]: # کاربران سطح ۱ یا ۲
    #      # Can only score their direct subordinates IF they have any
    #      if user.subordinates.exists():
    #          subordinates_to_check_for_missed = user.subordinates.all().exclude(is_active=False).order_by('first_name', 'last_name')
    #         #  print(f"User is Level {user.access_level} and has subordinates. Checking {subordinates_to_check_for_missed.count()} direct subordinates for missed daily scores.")
    #      else:
    #          pass
    #         #  print(f"User is Level {user.access_level} but has no subordinates. No missed daily scores opportunities will be shown.")
    #
    # # Access level 3 users do not score others daily
    #
    # if subordinates_to_check_for_missed.exists():
    #     today_jalali_obj_for_missed = jdatetime.date.today() # jdatetime.date
    #     current_j_year_missed = today_jalali_obj_for_missed.year
    #     current_j_month_missed = today_jalali_obj_for_missed.month
    #     past_days_in_current_j_month = []
    #
    #     # Iterate through past days in the current month (from 1st up to yesterday)
    #     if today_jalali_obj_for_missed.day > 1:
    #         first_day_of_j_month = jdatetime.date(current_j_year_missed, current_j_month_missed, 1)
    #         day_iterator = first_day_of_j_month
    #         while day_iterator < today_jalali_obj_for_missed:
    #             past_days_in_current_j_month.append(day_iterator)
    #             day_iterator += jdatetime.timedelta(days=1)
    #
    #     # Sort past days from newest to oldest for display
    #     past_days_in_current_j_month.reverse()
    #     # print(f"Checking {len(past_days_in_current_j_month)} past days ({[d.strftime('%Y/%m/%d') for d in past_days_in_current_j_month]}) in the current month.")
    #
    #     if past_days_in_current_j_month:
    #         past_gregorian_dates = [d.togregorian() for d in past_days_in_current_j_month]
    #         # print(f"Corresponding Gregorian dates: {[d.strftime('%Y-%m-%d') for d in past_gregorian_dates]}")
    #
    #         # Get all targets for these subordinates in the past days of the month with one query
    #         # Assuming Target.submission_date is DateTimeField or DateField, __date lookup works
    #         # If Target.submission_date is jmodels.jDateField, the filter should use jdatetime.date objects directly
    #         # e.g., Target.objects.filter(user__in=..., submission_date__in=past_days_in_current_j_month)
    #         targets_qs = Target.objects.filter(
    #              user__in=subordinates_to_check_for_missed,
    #              submission_date__date__in=past_gregorian_dates # Or submission_date__in=past_days_in_current_j_month if it's jDateField
    #         ).exclude(user__is_active=False).values('user_id', 'submission_date__date', 'content', 'submission_date') # Get full submission_date too
    #
    #         # Create a map for quick lookup: {(user_id, date): {target_content, full_submission_date}}
    #         targets_map = {}
    #         for t in targets_qs:
    #              # Ensure date key in map is Gregorian datetime.date for consistency with past_gregorian_dates
    #              target_date_gregorian = t['submission_date__date'] # This is already datetime.date from __date lookup
    #              targets_map[(t['user_id'], target_date_gregorian)] = {'content': t['content'], 'full_submission_date': t['submission_date']}
    #         # print(f"Found {len(targets_map)} targets submitted by eligible subordinates on past days matching Gregorian dates.")
    #
    #
    #         # Get all existing scores for these subordinates by the current manager in the past days
    #         # DailyManagerScore.date is jmodels.jDateField (stores as datetime.date internally)
    #         # So filtering by __in list of datetime.date objects should work
    #         existing_scores_qs = DailyManagerScore.objects.filter(
    #             manager=user,
    #             employee__in=subordinates_to_check_for_missed,
    #             date__in=past_gregorian_dates # Filtering jDateField by list of datetime.date
    #         ).exclude(employee__is_active=False).values('employee_id', 'date')
    #
    #         # Create a set of existing scores for quick lookup: {(employee_id, date)}
    #         # Ensure date key in set is Gregorian datetime.date for consistency
    #         existing_scores_set = set()
    #         for s in existing_scores_qs:
    #              score_date_gregorian = s['date'] # jDateField .values() returns datetime.date
    #              existing_scores_set.add((s['employee_id'], score_date_gregorian))
    #
    #         # print(f"Found {len(existing_scores_set)} existing scores given by current user for eligible subordinates on past days matching Gregorian dates.")
    #
    #         # Iterate through potential subordinates and past days to find missed opportunities
    #         # print("Iterating through subordinates and past days to find missed opportunities...")
    #         for sub_obj in subordinates_to_check_for_missed:
    #             for j_day_item in past_days_in_current_j_month:
    #                 gregorian_day_to_check = j_day_item.togregorian()
    #
    #                 # print(f"  Checking user {sub_obj.username} (ID: {sub_obj.id}) for date {gregorian_day_to_check.strftime('%Y-%m-%d')} (Jalali: {j_day_item.strftime('%Y/%m/%d')})...")
    #
    #                 # Check if a target exists for this user on this specific past day
    #                 target_key = (sub_obj.id, gregorian_day_to_check)
    #                 target_info = targets_map.get(target_key)
    #
    #                 if target_info:
    #                     # print(f"    Target found for {sub_obj.username} on {gregorian_day_to_check.strftime('%Y-%m-%d')}.")
    #                     # print(f"    Target submission date (full): {target_info['full_submission_date']}") # Print full datetime
    #
    #                     # Check if a score already exists for this user by this manager on this specific past day
    #                     score_key = (sub_obj.id, gregorian_day_to_check) # Using Gregorian date for key
    #                     score_already_exists = score_key in existing_scores_set
    #
    #                     if not score_already_exists:
    #                         # print(f"    Score NOT found by current user ({user.username}) for {sub_obj.username} on {gregorian_day_to_check.strftime('%Y-%m-%d')}. Adding opportunity.")
    #                         # Format Jalali date for display
    #                         jalali_date_str = j_day_item.strftime('%Y/%m/%d')
    #                         if sub_obj.access_level < 3 or user.access_level != -1:
    #                             missed_daily_scores_opportunities.append({
    #                                 'subordinate_name': f"{sub_obj.first_name} {sub_obj.last_name}",
    #                                 'employee_id': sub_obj.id,
    #                                 'jalali_date_str': jalali_date_str,
    #                                 'gregorian_date_to_submit': gregorian_day_to_check.strftime('%Y-%m-%d'),
    #                                 'target_content': target_info['content']
    #                             })
    #                     else:
    #                         pass
    #                         # print(f"    Score already EXISTS by current user ({user.username}) for {sub_obj.username} on {gregorian_day_to_check.strftime('%Y-%m-%d')}.")
    #                 else:
    #                     pass
    #                     # print(f"    No target found for {sub_obj.username} on {gregorian_day_to_check.strftime('%Y-%m-%d')}.")

    # print(f"Finished checking. Total missed daily scores opportunities found: {len(missed_daily_scores_opportunities)}")
    # +++ پایان بخش شناسایی فرصت‌های امتیازدهی روزهای گذشته +++


    # Condition to show the missed scores section: User is CEO/Board OR (User is Level 1 or 2 AND has subordinates) AND there are opportunities
    # should_show_missed_scores_section = (user.access_level in [0, -1] or (user.access_level in [1, 2] and user.subordinates.exists())) \
    #                                     and bool(missed_daily_scores_opportunities)
    # print(f"should_show_missed_scores_section: {should_show_missed_scores_section}")

    context = {
        "user": user,
        "current_year": current_year,
        "current_month": current_month,
        "current_day": current_day,

        # --- متغیرهای امتیاز روزانه (ساختار جدید و ساده‌شده) ---
        "subordinates": subordinates_for_template,  # فقط از این متغیر برای نمایش لیست امتیازدهی امروز استفاده می‌شود
        "today_daily_scores": today_daily_scores_for_template,
        # فقط از این متغیر برای چک کردن امتیازات ثبت‌شده امروز استفاده می‌شود
        "today_year": current_year,
        "today_month": current_month,
        "today_day": current_day,

        # --- متغیرهای امتیازدهی روزهای گذشته ---
        "missed_daily_scores_opportunities": missed_daily_scores_opportunities,
        "should_show_missed_scores_section": should_show_missed_scores_section,

        # --- متغیرهای امتیاز ماهانه (برای جلوگیری از خطا در تمپلیت) ---
        "users": all_other_users_monthly,
        "score_dict": score_dict_from_db,
        "existing_scores_by_user": existing_scores_by_user_map,
        "monthly_scores_finalized": monthly_scores_finalized,
        "access_level": user.access_level,
        "year": current_year,
        "month": current_month,

        # --- متغیرهای اهداف و امتیازات خود کاربر (بدون تغییر) ---
        "my_scores_targets": my_scores_targets_for_template,
        "monthly_targets_count": monthly_targets_count_for_template,
        "my_sum_scores": my_sum_scores_for_template,

        # "targets_subordinates_pre": targets_subordinates_pre_for_template, # متغیر اصلی شما (targets of Level 2 manager's subordinates excluding today)
        # برای بخش امتیازدهی روزهای گذشته
        # "missed_daily_scores_opportunities": missed_daily_scores_opportunities,
        # "should_show_missed_scores_section": should_show_missed_scores_section,
    }
    return render(request, "accounts/dashboard.html", context)
    # raise PermissionDenied()


@login_required
@csrf_exempt
@require_POST
def submit_daily_score(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            employee_id = data.get("employee_id")
            value = data.get("value")
            score_date_str = data.get("score_date")

            if employee_id is None or value is None:
                return JsonResponse({"status": "error", "error": "داده‌های employee_id و value الزامی هستند."}, status=400)
            try:
                employee_id = int(employee_id)
                value = int(value)
            except (ValueError, TypeError):
                return JsonResponse({"status": "error", "error": "مقادیر employee_id و value باید عدد صحیح باشند."}, status=400)

            # Validate score value
            if not (1 <= value <= 10):
                return JsonResponse({"status": "error", "error": f"مقدار امتیاز روزانه ({value}) باید بین ۱ تا ۱۰ باشد."}, status=400)

            date_for_score_save = None
            if score_date_str:
                try:
                    # Parse the date string assuming
                        # ```python
                    # Parse the date string assuming YYYY-MM-DD Gregorian format
                    date_for_score_save = python_datetime.strptime(score_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({"status": "error", "error": "فرمت تاریخ ارسالی نامعتبر است. باید YYYY-MM-DD میلادی باشد."}, status=400)
            else:
                # If score_date is not provided, assume it's for today
                # Need to get today's date in the correct timezone and convert to date object
                try:
                    iran_tz = pytz.timezone("Asia/Tehran")
                except pytz.UnknownTimeZoneError:
                    iran_tz = timezone.get_default_timezone() # Fallback
                date_for_score_save = timezone.now().astimezone(iran_tz).date()

            # --- منطق بررسی مجوز ثبت امتیاز (بازنویسی شده) ---
            scorer = request.user
            try:
                employee = CustomUser.objects.get(id=employee_id)
            except CustomUser.DoesNotExist:
                return JsonResponse({"status": "error", "error": "کارمند مورد نظر یافت نشد."}, status=404)

            is_authorized = False
            # استثنای خاص: کاربر ۷۳ می‌تواند به کاربر ۶۸ امتیاز دهد
            # if scorer.id == 73 and employee.id == 68:
            #     is_authorized = True
            # بررسی قوانین عمومی در صورتی که استثنا برقرار نباشد
            # else:
            # هیئت مدیره (-۱) به مدیرعامل (۰) و مدیران میانی (۱)
            if (scorer.access_level == -1 and employee.access_level in [0, 1]) or (scorer.id == 73 and employee.supervisor.id == 68):
                is_authorized = True
            # مدیرعامل (۰) به مدیران میانی (۱) و سرپرستان (۲)
            elif scorer.access_level == 0 and employee.access_level in [1, 2]:
                is_authorized = True
            # مدیران میانی (۱) و سرپرستان (۲) به زیرمجموعه‌های مستقیم
            elif scorer.access_level in [1, 2] and employee.supervisor == scorer:
                is_authorized = True

            # جلوگیری از امتیازدهی به کاربر ۶۸ توسط دیگران
            # if employee.id == 68 and scorer.id != 73:
            if employee.id == 68:
                is_authorized = False

            if not is_authorized:
                return JsonResponse(
                    {"status": "unauthorized", "error": "شما مجاز به ثبت امتیاز برای این کارمند نیستید."}, status=403)

            # Prevent scoring for future dates
            try:
                iran_tz = pytz.timezone("Asia/Tehran")
            except pytz.UnknownTimeZoneError:
                iran_tz = timezone.get_default_timezone() # Fallback
            today_date_iran = timezone.now().astimezone(iran_tz).date()

            if date_for_score_save > today_date_iran:
                 return JsonResponse({"status": "error", "error": "نمی‌توانید برای تاریخ‌های آینده امتیاز ثبت کنید."}, status=400)

            # دریافت تاریخ برای ذخیره امتیاز
            date_for_score_save = None
            if score_date_str:
                date_for_score_save = python_datetime.strptime(score_date_str, '%Y-%m-%d').date()
            else:
                date_for_score_save = timezone.now().astimezone(iran_tz).date()

             # جلوگیری از ثبت امتیاز تکراری
            if DailyManagerScore.objects.filter(manager=scorer, employee=employee, date=date_for_score_save).exists():
                 return JsonResponse(
                     {"status": "duplicate", "error": f"شما قبلاً برای این تاریخ به این کارمند امتیاز داده‌اید."},
                     status=400)

            # ایجاد امتیاز
            DailyManagerScore.objects.create(manager=scorer, employee=employee, date=date_for_score_save, value=value)

            return JsonResponse({"status": "ok", "message": f"امتیاز با موفقیت ثبت شد."})

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "error": "فرمت داده ارسالی نامعتبر (JSON نامعتبر)."}, status=400)
        except Exception as e:
            logging.error(f"Unexpected error in submit_daily_score: {e}")
            return JsonResponse({"status": "error", "error": f"خطای سرور داخلی: {str(e)}"}, status=500)

    return JsonResponse({"status": "invalid_method", "error": "این endpoint فقط درخواست‌های POST را می‌پذیرد."},
                            status=405)


def under_construction(request):
    return render(request, 'under_construction.html')


def is_score_type_allowed(access_level, score_type, user, jdt_now):
    # print(jnow , jdt_datetime.fromgregorian(datetime=user.date_joined).astimezone(iran_tz))
    if not (jdt_now > jdt_datetime.fromgregorian(datetime=user.date_joined).astimezone(iran_tz)):
        return False

    allowed_types = {
        -1: [1, 2, 3, 0],
        0: [1, 2, 3],
        1: [1, 2, 3],
        2: [1, 2],
        3: [1],
    }
    return score_type in allowed_types.get(access_level, [])


@login_required
@csrf_exempt
@require_POST
def update_monthly_scores(request):
    if request.method == "POST":
        data = json.loads(request.body)
        date = get_jalali_date()
        year = date[0]
        month = date[1]
        counter = 0

        for item in data.get("scores", []):
            target_id = item["target_id"]
            score_type = int(item["score_type"])
            value = int(item["value"])

            if not is_score_type_allowed(request.user.access_level, score_type, request.user, jnow):
                continue

            try:
                counter+=1
                MonthlyScore.objects.update_or_create(
                    scorer=request.user,
                    target_id=target_id,
                    score_type=score_type,
                    year=year,
                    month=month,
                    defaults={"value": value},
                )
            except Exception as e:
                return JsonResponse({"status": "error", "error": str(e)})

        if counter != 0:
            return JsonResponse({"status": "ok"})
        else:
            return JsonResponse({"status": "forbidden", "error": "شما مجاز به ثبت امتیاز نیستید"}, status=403)
    return JsonResponse({"status": "forbidden"}, status=403)


FILE_ICON_MAP = {
    "pdf": ("fas fa-file-pdf", "pdf"),
    "doc": ("fas fa-file-word", "word"),
    "docx": ("fas fa-file-word", "word"),
    "txt": ("fas fa-file-alt", "text"),
    "jpg": ("fas fa-file-image", "image"),
    "jpeg": ("fas fa-file-image", "image"),
    "png": ("fas fa-file-image", "image"),
    "zip": ("fas fa-file-archive", "archive"),
    "rar": ("fas fa-file-archive", "archive"),
    "xls": ("fas fa-file-excel", "excel"),
    "xlsx": ("fas fa-file-excel", "excel"),
    "default": ("fas fa-file", "default"),
}

@login_required
def knowledge_management(request):
    user = request.user

    # دسترسی به MAX_FILE_SIZE از کلاس فرم
    max_file_size_from_form = KnowledgeManagementForm.MAX_FILE_SIZE
    allowed_extensions_from_form = KnowledgeManagementForm.ALLOWED_EXTENSIONS

    if request.method == 'POST':
        form = KnowledgeManagementForm(request.POST, request.FILES)
        if form.is_valid():
            km_item = form.save(commit=False)
            km_item.user = user
            km_item.save()
            return redirect('knowledge_management')
    else:
        form = KnowledgeManagementForm()

    km_entries = UserKnowledgeManagement.objects.filter(user=user).exclude(user__is_active=False).order_by('-created_at_jalali')

    allowed_extensions_for_accept = [f".{ext}" for ext in allowed_extensions_from_form]
    accept_string = ",".join(allowed_extensions_for_accept)

    context = {
        'km_entries': km_entries,
        'form': form,
        'allowed_extensions': allowed_extensions_from_form,
        'max_file_size_mb': max_file_size_from_form / (1024 * 1024),
        'max_file_size_bytes': max_file_size_from_form, # این را به JS پاس می‌دهیم
        'file_icon_map': FILE_ICON_MAP,
        "icon_types": [('pdf', "پی دی اف"), ('word', "ورد"), ('text', "متن"), ('image', "تصویر"), ('archive', "آرشیو"), ('excel', "اکسل"), ('default', "پیش فرض")],
        'accept_file_types': accept_string,
    }
    return render(request, 'accounts/knowledge_management.html', context)


@login_required
def delete_knowledge_management_item_view(request, item_id):
    """حذف یک مورد مدیریت دانش خاص."""
    # واکشی مورد مورد نظر و اطمینان از اینکه متعلق به کاربر لاگین شده است
    item = get_object_or_404(UserKnowledgeManagement, id=item_id, user=request.user)

    if request.method == 'POST':
        item.delete()
        # messages.success(request, "مورد مدیریت دانش با موفقیت حذف شد.")
        return redirect('knowledge_management') # <--- Redirect صحیح بدون namespace

    return redirect('knowledge_management') # یا HttpResponseBadRequest("Invalid request method")


@login_required
def edit_knowledge_management_item_view(request, item_id):
    """ویرایش یک مورد مدیریت دانش خاص."""
    # واکشی مورد مورد نظر و اطمینان از اینکه متعلق به کاربر لاگین شده است
    item = get_object_or_404(UserKnowledgeManagement, id=item_id, user=request.user)

    if request.method == 'POST':
        form = KnowledgeManagementForm(request.POST, instance=item) # استفاده از فرم صحیح
        if form.is_valid():
            form.save()
            # messages.success(request, "مورد مدیریت دانش با موفقیت بروزرسانی شد.")
            return redirect('knowledge_management') # <--- Redirect صحیح بدون namespace
    else:
        form = KnowledgeManagementForm(instance=item) # استفاده از فرم صحیح

    context = {
        'form': form,
        'item': item,
    }
    # نیاز به تمپلت edit_km_item.html دارد (اگر این View را فعال کردید)
    return render(request, 'accounts/edit_km_item.html', context)


@login_required
def user_responsibilities_view(request):
    user = request.user
    responsibilities = UserResponsibility.objects.filter(user=user).order_by('order', 'responsibility_type')

    # واکشی آیین‌نامه‌های فعال
    active_regulations = RegulationDocument.objects.filter(is_active=True).order_by('order', 'title')

    user_regulation_statuses = {}
    read_regulations_count = 0
    for reg in active_regulations:
        # برای هر آیین‌نامه، وضعیت مطالعه کاربر را بگیرید یا ایجاد کنید
        ack, created = UserRegulationAcknowledgement.objects.get_or_create(
            user=user,
            regulation=reg
        )
        user_regulation_statuses[reg.id] = ack
        if ack.is_read:
            read_regulations_count += 1

    # وضعیت تاییدیه کلی کاربر را بگیرید یا ایجاد کنید
    overall_ack, created = UserOverallRegulationAcknowledgement.objects.get_or_create(user=user)

    # بررسی اینکه آیا همه آیین‌نامه‌های فعال جاری توسط کاربر به صورت انفرادی مطالعه شده‌اند
    all_current_regulations_individually_read = False
    if active_regulations.exists():  # فقط اگر آیین‌نامه‌ای فعال وجود داشته باشد
        all_current_regulations_individually_read = (read_regulations_count == active_regulations.count())

    context = {
        'responsibilities': responsibilities,
        'active_regulations': active_regulations,
        'user_regulation_statuses': user_regulation_statuses,  # دیکشنری: {regulation_id: ack_object}
        'overall_acknowledgement_record': overall_ack,  # آبجکت UserOverallRegulationAcknowledgement
        'all_current_regulations_individually_read': all_current_regulations_individually_read,
        'total_active_regulations': active_regulations.count(),
    }
    return render(request, 'accounts/user_responsibilities.html', context)


@login_required
@require_POST
def toggle_regulation_read_status(request):
    user = request.user
    regulation_id = request.POST.get('regulation_id')

    if not regulation_id:
        return JsonResponse({'success': False, 'error': 'شناسه آیین‌نامه ارسال نشده است.'}, status=400)

    try:
        regulation_id = int(regulation_id)
        regulation = get_object_or_404(RegulationDocument, id=regulation_id, is_active=True)
    except (ValueError, RegulationDocument.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'آیین‌نامه معتبر نیست یا یافت نشد.'}, status=404)

    acknowledgement, created = UserRegulationAcknowledgement.objects.get_or_create(
        user=user,
        regulation=regulation
    )

    # تغییر وضعیت مطالعه
    acknowledgement.is_read = not acknowledgement.is_read
    if acknowledgement.is_read:
        acknowledgement.read_at = timezone.now()
    else:
        acknowledgement.read_at = None  # اگر "خوانده نشده" شد، تاریخ را پاک کن
    acknowledgement.save()

    # پس از تغییر، بررسی کن آیا همه آیین‌نامه‌های فعال جاری خوانده شده‌اند یا نه
    active_regulations_count = RegulationDocument.objects.filter(is_active=True).count()
    read_count_after_toggle = UserRegulationAcknowledgement.objects.filter(
        user=user,
        regulation__is_active=True,
        is_read=True
    ).count()

    all_individually_read_now = False
    if active_regulations_count > 0:
        all_individually_read_now = (read_count_after_toggle == active_regulations_count)

    return JsonResponse({
        'success': True,
        'regulation_id': regulation.id,
        'is_read': acknowledgement.is_read,
        'read_at': acknowledgement.read_at.astimezone(iran_tz).strftime('%Y-%m-%d %H:%M') if acknowledgement.read_at else None,
        'all_current_individually_read': all_individually_read_now
    })


@login_required
@require_POST
def confirm_all_regulations_read(request):
    user = request.user

    active_regulations = RegulationDocument.objects.filter(is_active=True)
    if not active_regulations.exists():
        # اگر هیچ آیین‌نامه فعالی وجود ندارد، تایید کلی معنا ندارد یا به صورت پیش‌فرض موفق است
        # این حالت را بر اساس نیاز خود مدیریت کنید. اینجا فرض می‌کنیم اگر آیین‌نامه‌ای نیست، تایید موفق است.
        overall_ack, created = UserOverallRegulationAcknowledgement.objects.get_or_create(user=user)
        overall_ack.all_regulations_confirmed = True  # یا False، بسته به سیاست شما
        overall_ack.confirmation_date = timezone.now().astimezone(iran_tz) if overall_ack.all_regulations_confirmed else None
        overall_ack.save()
        return JsonResponse({'success': True, 'message': 'هیچ آیین‌نامه فعالی برای تایید وجود ندارد.',
                             'all_confirmed': overall_ack.all_regulations_confirmed})

    # بررسی مجدد سمت سرور که آیا همه آیین‌نامه‌های فعال خوانده شده‌اند
    read_confirmations = UserRegulationAcknowledgement.objects.filter(
        user=user,
        regulation__in=active_regulations,
        is_read=True
    ).count()

    if read_confirmations == active_regulations.count():
        overall_ack, created = UserOverallRegulationAcknowledgement.objects.get_or_create(user=user)
        overall_ack.all_regulations_confirmed = True
        overall_ack.confirmation_date = timezone.now()
        overall_ack.confirmation_date.astimezone(iran_tz)
        # snapshots = [reg.id for reg in active_regulations] # اگر می‌خواهید لیست IDها را ذخیره کنید
        # overall_ack.confirmed_regulations_snapshot = {'ids': snapshots, 'count': len(snapshots)}
        overall_ack.save()
        return JsonResponse({'success': True, 'message': 'تاییدیه کلی با موفقیت ثبت شد.', 'all_confirmed': True,
                             'confirmation_date': overall_ack.confirmation_date.strftime('%Y-%m-%d %H:%M')})
    else:
        # اگر کاربر سعی در تایید کلی دارد ولی همه را نخوانده، تاییدیه کلی را False می‌کنیم
        overall_ack, created = UserOverallRegulationAcknowledgement.objects.get_or_create(user=user)
        overall_ack.all_regulations_confirmed = False
        overall_ack.confirmation_date = None
        overall_ack.save()
        return JsonResponse({'success': False, 'error': 'شما هنوز تمام آیین‌نامه‌های فعال را مطالعه نکرده‌اید.'},
                            status=400)


def user_is_allowed(user):
    return user.id in [61, 1, 55] or user.access_level in [0, -1]


def get_monthly_performance_data(request):
    year = int(request.GET.get("year", jdt_datetime.now().year))
    month = int(request.GET.get("month", jdt_datetime.now().month))

    start_jdate = jdt_datetime(year, month, 1)
    if month == 12:
        end_jdate = jdt_datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_jdate = jdt_datetime(year, month + 1, 1, 23, 59, 59) - timedelta(days=1)

    start_gregorian = start_jdate.togregorian()
    end_gregorian = end_jdate.togregorian()

    group_to_section = {
        "کارمند حسابداری صنعتی": "بخش حسابداری صنعتی",
        "سرپرست حسابداری صنعتی": "بخش حسابداری صنعتی",
        "انبار دار": "بخش حسابداری صنعتی",
        "سرپرست حسابداری": "بخش حسابداری",
        "کارمند حسابداری": "بخش حسابداری",
        "کارمند IT": "بخش IT",
        "سرپرست IT": "بخش IT",
        "سرپرست مالی اداری": "بخش مالی اداری",
        "نیروی خدمات": "بخش مالی اداری",
        "مدیر عامل شرکت برنا": "برنا",
        "کارمند برنا": "برنا",
        "کارمند صنایع برنا": "برنا",
        "مدیر بخش حقوقی": "بخش حقوقی",
        "کارمند مونتاژ": "بخش مونتاژ",
        "سرپرست مونتاژ": "بخش مونتاژ",
        "سرپرست کنترل کیفی و تنخواه گردان": "بخش کنترل کیفی و تنخواه گردان",
        "کارمند کنترل کیفی": "بخش کنترل کیفی و تنخواه گردان",
        "سرپرست آبکاری": "بخش آبکاری",
        "کارمند آبکاری": "بخش آبکاری",
        "سرپرست بازرگانی خارجی": "بخش بازرگانی خارجی",
        "کارمند بازرگانی خارجی": "بخش بازرگانی خارجی",
        "کارمند تراش": "بخش تراش",
        "سرپرست تراش": "بخش تراش",
    }

    users = CustomUser.objects.prefetch_related('groups').exclude(
        Q(id__in=not_allowed_ids) | Q(access_level__lt=1) | Q(is_active=False)
    )

    group_definitions = defaultdict(list)

    for user in users:
        name = user.groups.first().name
        section = group_to_section.get(name)
        if section:
            group_definitions[section].append(user)


    performance_data = []

    for user in users:
        targets_count = Target.objects.filter(user=user,
                                              submission_date__range=(start_gregorian, end_gregorian)).exclude(user__is_active=False).count()

        # TODO: Calculate daily scores with specified  formula
        if request.user.access_level in [0, -1] or request.user.id in [61, 1]:
            total_score = DailyManagerScore.objects.filter(
                employee=user,
                date__gte=start_jdate.date(),
                date__lte=end_jdate.date()
            ).aggregate(total=Sum('value'))['total'] or 0

            calculated_scores = 1
        else:
            calculated_scores = None
            total_score = None

        performance_data.append({
            "user": user,
            "targets_count": targets_count,
            "total_score": total_score,
            "calculated_scores": calculated_scores,
        })

    performance_data = sorted(performance_data, key=lambda x: [x['targets_count'], x["total_score"] if x["total_score"] is not None else -1], reverse=True)

    # Group performance data
    overall_actual_score_sum = 0
    overall_potential_score_sum = 0
    grouped_performance_data = []
    for group_name, group_users in group_definitions.items():
        if not group_users:
            continue

        group_total_targets = 0
        group_total_actual_score = 0
        group_total_potential_score = 0

        for user_in_group in group_users:
            # Find the performance data for this user
            user_perf = next((item for item in performance_data if item['user'].id == user_in_group.id), None)
            if user_perf:
                if request.user.access_level in [0, -1] or request.user.id in [61, 1]:
                    group_total_targets += user_perf['targets_count']
                    group_total_actual_score += user_perf['total_score'] if user_perf['total_score'] is not None else 0
                    # Assuming each target can yield a max of 10 points (as per your example)
                    group_total_potential_score += (user_perf['targets_count'] * 10)
                else:
                    group_total_targets = group_total_actual_score = group_total_potential_score = 0

        # Add group data if there are users in the group
        if group_users:
            grouped_performance_data.append({
                "group_name": group_name,
                "user_count": len(group_users),
                "group_total_targets": group_total_targets,
                "group_total_actual_score": group_total_actual_score,
                "group_total_potential_score": group_total_potential_score,
            })
            overall_actual_score_sum += group_total_actual_score
            overall_potential_score_sum += group_total_potential_score

    grouped_performance_data = sorted(grouped_performance_data, key=lambda x: x['group_total_potential_score'], reverse=True)

    return performance_data, grouped_performance_data, (year, month), (overall_actual_score_sum, overall_potential_score_sum)


@login_required
@require_GET
@user_passes_test(user_is_allowed)
def user_monthly_performance(request):
    performance_data_tuple = get_monthly_performance_data(request)
    performance_data_page = performance_data_tuple[0]
    grouped_performance_data = performance_data_tuple[1]
    year, month = performance_data_tuple[2]
    overall_scores = performance_data_tuple[3]

    match request.GET.get("export"):
        case "pdf":
            return export_monthly_pdf(request, performance_data_page, grouped_performance_data, year, month, overall_scores)
        case "excel":
            return export_monthly_excel(request, performance_data_page, grouped_performance_data, year, month, overall_scores)

    data_for_chart = [
        {
            'name': p['user'].get_full_name(),
            'score': p['total_score'],
            "count": p["targets_count"],
            "calculated_scores": p["calculated_scores"]
        }
        for p in performance_data_page
    ]

    return render(request, 'accounts/monthly_performance.html', {
        'performance_data': performance_data_page,
        "grouped_performance_data": grouped_performance_data,
        "overall_scores": overall_scores,
        'selected_year': year,
        'selected_month': month,
        'chart_labels': mark_safe(json.dumps([p['name'] for p in data_for_chart])),
        'chart_scores': mark_safe(json.dumps([p['score'] for p in data_for_chart])),
        "targets_count": mark_safe(json.dumps([p['count'] for p in data_for_chart])),
        "calculated_scores": mark_safe(json.dumps([p['calculated_scores'] for p in data_for_chart])),
    })


def export_monthly_pdf(request, performance_data, grouped_performance_data_pdf, year, month, overall_scores):
    performance_data_pdf = performance_data
    year = year
    month = month

    # Determine the absolute path to your font file
    # This assumes your font is in 'accounts/static/fonts/vazirmatn/Vazirmatn-Medium.ttf'
    # Adjust 'accounts' if your app name is different.
    # Adjust the font file name if necessary (e.g., Vazirmatn-Medium.woff2).
    font_filename = 'Vazirmatn-Medium.woff2'
    font_format = 'truetype' # or 'woff2' if using a .woff2 file

    # Path relative to an app's static directory
    # Assuming your app containing the template and static files is 'accounts'
    app_name = 'accounts'
    try:
        # Path for fonts within an app's static directory: <BASE_DIR>/<app_name>/static/fonts/...
        font_path = os.path.join(settings.BASE_DIR, app_name, 'static', 'fonts', 'vazirmatn', font_filename)
        if not os.path.exists(font_path):
            # Fallback: Check if font is directly under a directory listed in STATICFILES_DIRS
            # This requires more specific knowledge of your STATICFILES_DIRS setup.
            # For simplicity, we'll assume the app static directory structure first.
            # If your fonts are in a global static dir, adjust path accordingly.
            # e.g., os.path.join(settings.STATICFILES_DIRS[0], 'fonts', 'vazirmatn', font_filename)
            # This part might need adjustment based on your exact static files setup.
            # A common setup is having fonts in an app's 'static' folder.
            raise FileNotFoundError # Trigger error if not found with primary path strategy
    except (AttributeError, FileNotFoundError): # AttributeError if settings.BASE_DIR is not found (unlikely in full Django)
        # Handle error: font path could not be determined
        # You might want to log this or return an error response
        return HttpResponse("Error: Font file path could not be determined.", status=500)

    vazirmatn_font_url = 'file://' + font_path.replace('\\', '/') # Ensure forward slashes for URI

    context = {
        'performance_data': performance_data_pdf,
        'grouped_performance_data': grouped_performance_data_pdf,
        "overall_scores": overall_scores,
        'selected_year': year,
        'selected_month': month,
        'vazirmatn_font_url': vazirmatn_font_url,
        'vazirmatn_font_format': font_format,
    }
    html_string = render_to_string('accounts/monthly_performance_pdf.html', context)

    # The base_url is still useful for other relative assets like images,
    # but for fonts, the file:// path is more direct.
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=monthly_performance_{year}_{month}.pdf'
    return response


def export_monthly_excel(request, performance_data_excel, grouped_performance_data_excel, year, month, overall_scores):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "عملکرد ماهانه افراد"
    ws.append(["#", "نام کاربر", "تعداد اهداف", "مجموع امتیاز", "مجموع امتیاز(محاسبه شده توسط فرمول)"])

    for i, item in enumerate(performance_data_excel, 1):
        ws.append([i, item['user'].get_full_name(), item['targets_count'], item['total_score'], item["calculated_scores"]])

    # Sheet for grouped performance
    ws_grouped = wb.create_sheet("عملکرد ماهانه گروه ها")
    ws_grouped.append(["نام گروه", "تعداد کاربران", "مجموع اهداف", "مجموع امتیاز کسب شده", "مجموع امتیاز بالقوه"])

    for item in grouped_performance_data_excel:
        ws_grouped.append([
            item['group_name'],
            item['user_count'],
            item['group_total_targets'],
            item['group_total_actual_score'],
            item['group_total_potential_score'],
        ])

    ws_grouped.append([
        "",
        "",
        "",
        overall_scores[0],
        overall_scores[1],
    ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=monthly_performance_{year}_{month}.xlsx'
    wb.save(response)
    return response


def user_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)


        if user is not None:
            login(request, user) # ورود کاربر
            # messages.success(request, f'خوش آمدید، {user.username}!')
            return redirect('dashboard')

        else:
            try:
                potential_user = CustomUser.objects.get(username=username)

                if not potential_user.is_active:
                    messages.error(request, 'حساب کاربری شما فعال نیست. لطفا با پشتیبانی تماس بگیرید.')
                else:
                    messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')

            except CustomUser.DoesNotExist:
                messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
            except Exception as e:
                messages.error(request, 'خطایی در هنگام ورود رخ داد. لطفا مجددا تلاش کنید.')
                print(e)
                logger = logging.getLogger()
                logger.error(f"Error during login user check: {e}")


            # در هر صورت (شکست لاگین، کاربر غیرفعال، نام کاربری اشتباه)،
            # دوباره صفحه لاگین را رندر کن.
            # پیام خطا قبلا با messages.error اضافه شده است.
            return render(request, 'accounts/login.html')


    return render(request, 'accounts/login.html')


from django.contrib.sessions.models import Session
def single_session_login(request, user):
    # حذف سشن‌های قدیمی این کاربر
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id):
            session.delete()
    login(request, user)


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def protected_media_view(request, user_id, path):
    if request.user.id != user_id:
        raise PermissionError("اجازه دسترسی ندارید.")

    full_path = os.path.join(settings.MEDIA_ROOT, f'knowledge_management_files/user_{user_id}/{path}')
    if not os.path.exists(full_path):
        raise Http404("فایل پیدا نشد.")

    return FileResponse(open(full_path, 'rb'))


@login_required
def protected_media_view_req(request, path):
    full_path = f'{settings.MEDIA_ROOT}/regulations/{path}'

    print(full_path)
    if not os.path.exists(full_path):
        raise Http404("فایل پیدا نشد.")

    return FileResponse(open(full_path, 'rb'))