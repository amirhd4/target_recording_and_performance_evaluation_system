from PIL.ImageMath import lambda_eval
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from products.models import Project, Product, ProductionOrder, InventoryItem
from .models import Target, TaskType # TaskType احتمالاً باید یک مدل جداگانه برای وظایف کلی باشد
from accounts.models import CustomUser
from django.contrib.auth.models import Group
from jdatetime import datetime as jdatetime
from django.db.models import Value, F, Q
from django.db.models.functions import Concat
from django.utils import timezone
from pytz import timezone as tz
from accounts.utils import utils
from datetime import timedelta, datetime as python_datetime
from urllib import parse
import pytz
import subprocess
from celery import shared_task


def submit_target_view(request):
    # این `task_types` دیگر برای فیلدهای دینامیک عمومی استفاده نمی‌شود،
    # اما ممکن است برای فیلتر کردن دسترسی به فرم جدید پروژه کاربرد داشته باشد.
    # فرض بر این است که فقط کاربرانی که به ProductionOrder ها مرتبط هستند
    # یا در گروه های خاصی هستند، باید این فرم را ببینند.

    active_statuses = [
        ProductionOrder.StatusChoices.PENDING,
        ProductionOrder.StatusChoices.IN_PROGRESS
    ]

    # بخش اول: گرفتن لیست تمام گروه‌های فعال
    allowed_groups_qs = Group.objects.filter(
        production_tasks__status__in=active_statuses
    ).distinct()

    # سپس فقط نام‌ها را به صورت لیستی از رشته‌ها استخراج می‌کنیم
    allowed_groups = allowed_groups_qs.values_list('name', flat=True)


    # بخش دوم: چک کردن دسترسی کاربر فعلی (سریع و بهینه)
    user_can_access_project_form = request.user.groups.filter(
        production_tasks__status__in=active_statuses
    ).exists()

    if request.method == 'POST':
        response = redirect('submit_target')
        full_name = request.POST.get('full_name', '').strip()
        date_str = request.POST.get('date', '').strip()
        expected_format = "%Y/%m/%d"

        try:
            submitted_jalali_date = jdatetime.strptime(date_str, expected_format).date()
        except ValueError:
            messages.error(request, "فرمت تاریخ وارد شده نامعتبر است. لطفاً از فرمت YYYY/MM/DD استفاده کنید.")
            return redirect("submit_target")
        except Exception as e:
            print(e)
            messages.error(request, "مشکل در تاریخ وارد شده. لطفاً مجدداً تلاش کنید.")
            return redirect("submit_target")

        if not full_name:
            messages.warning(request, "لطفاً نام و نام خانوادگی خود را انتخاب کنید.")
            return response

        user_instance = None
        try:
            user_instance = CustomUser.objects.annotate(
                full_name=Concat(F("first_name"), Value(" "), F("last_name"))
            ).get(
                full_name__iexact=full_name
            )
        except CustomUser.DoesNotExist:
            messages.error(request, f"کاربری با نام '{full_name}' در سامانه یافت نشد.")
            return response
        except CustomUser.MultipleObjectsReturned:
            messages.error(request, f"چند کاربر با نام '{full_name}' یافت شد. لطفاً با مدیر سیستم تماس بگیرید.")
            return response
        except Exception:
            messages.error(request, "خطا در جستجوی کاربر. لطفاً مجدداً تلاش کنید.")
            return response

        if user_instance:
            target_content_parts = []

            # --- پردازش فیلدهای پروژه‌ها و سفارشات تولید ---
            # فقط در صورتی پردازش می‌شود که کاربر اجازه دسترسی به این فرم را داشته باشد
            # --- پردازش فیلدهای پروژه‌ها و سفارشات تولید ---
            if user_can_access_project_form:
                selected_project_ids = request.POST.getlist("selected_projects", [])
                projects_data = []

                # Fetch all relevant production orders once for efficiency
                # We need to fetch all orders that belong to the selected projects
                # AND are assigned to the user's groups.
                # Also prefetch the 'product' ManyToMany field.
                all_relevant_production_orders = ProductionOrder.objects.filter(
                    project__id__in=selected_project_ids,
                    assigned_to__in=user_instance.groups.all(),
                    status__in=[ProductionOrder.StatusChoices.PENDING, ProductionOrder.StatusChoices.IN_PROGRESS]
                ).prefetch_related('product', 'project').distinct()  # prefetch products and projects

                # Create a dictionary for quick lookup by order ID
                # orders_by_id = {order.id: order for order in all_relevant_production_orders}

                for project_id in selected_project_ids:
                    try:
                        project = Project.objects.get(id=project_id)  # Re-fetch project to get its name for display
                        project_info = {"name": project.name, "products": []}

                        # Filter production orders relevant to this specific project_id
                        project_production_orders = [
                            order for order in all_relevant_production_orders
                            if order.project.id==project.id  # Check if this project is linked
                        ]

                        for order in project_production_orders:
                            for product_instance in order.product.all():  # Iterate through each product in the ManyToMany
                                input_name = f"production_order_{order.id}_{product_instance.id}"  # Match new input name
                                if value := request.POST.get(input_name, '').strip():
                                    try:
                                        quantity_entered = int(value)
                                        # Validate quantity against a suitable max (e.g., order.quantity or product-specific if a through model is used)
                                        if 0 <= quantity_entered <= order.quantity + 1:
                                            project_info["products"].append({
                                                "product_name": product_instance.name,
                                                "order_quantity": order.quantity,  # This is the overall order quantity
                                                "produced_quantity": quantity_entered,
                                                "unit": product_instance.category.unit if product_instance.category and product_instance.category.unit else "",
                                                "order_id": order.id,
                                                "product_id": product_instance.id,
                                                # Keep track of product ID for this entry
                                            })
                                            InventoryItem.objects.create(
                                                user=user_instance,
                                                product=product_instance,
                                                project=project,
                                                quantity=quantity_entered
                                            )
                                            # TODO: اینجا می‌توانید منطق به‌روزرسانی ProductionOrder (مثلاً میزان پیشرفت) یا ProductionOrderItem را اضافه کنید
                                            # If you use a ProductionOrderItem (through model), you'd update its quantity_produced.
                                            # If not, you'll need to define how `quantity_entered` impacts the `ProductionOrder.quantity` or a new 'progress_made' field on ProductionOrder.
                                            # Example: order.progress_made += quantity_entered (if you add this field)
                                            # Example: order.save()
                                        else:
                                            messages.warning(request,
                                                             f"مقدار وارد شده برای محصول {product_instance.name} در پروژه {project.name} نامعتبر است.")
                                            return response
                                    except ValueError:
                                        messages.warning(request,
                                                         f"مقدار وارد شده برای محصول {product_instance.name} در پروژه {project.name} باید عددی باشد.")
                                        return response

                        if project_info["products"]:
                            projects_data.append(project_info)
                    except Project.DoesNotExist:
                        pass

                # Add project and product info to target_content_parts
                if projects_data:
                    for project_data in projects_data:
                        target_content_parts.append(f"پروژه: {project_data['name']}")
                        for prod_entry in project_data['products']:
                            target_content_parts.append(
                                f"  - محصول: {prod_entry['product_name']} تولید شده: {prod_entry['produced_quantity']} {prod_entry['unit']}")
                    target_content_parts.append("\n")

                # منطق فیلدهای داینامیک (اختیاری) - اگر همچنان نیاز دارید
                custom_titles = request.POST.getlist('custom_title')
                custom_values = request.POST.getlist('custom_value')
                for title, value in zip(custom_titles, custom_values):
                    if title.strip() and value.strip():
                        target_content_parts.append(f"{title.strip()}:\n {value.strip()}\n")

                if extra_notes := request.POST.get('extra_notes', '').strip():
                    target_content_parts.append(f"\nتوضیحات تکمیلی:\n{extra_notes}")
            else: # اگر کاربر دسترسی به فرم پروژه ندارد، از فیلد `target_text` استفاده کنید
                if content := request.POST.get('target_text', '').strip():
                    target_content_parts.append(content)

            target_content = "\n".join(target_content_parts)

            if not target_content:
                messages.warning(request, "محتوای هدف نمی‌تواند خالی باشد.")
                return response

            if request.POST.get("save_cookie") == "1":
                response.set_cookie(
                    'target_text',
                    parse.quote(target_content),
                    expires=3600 * 24 * 20
                )
            else:
                response.delete_cookie('target_text')

            try:
                iran_tz = tz("Asia/Tehran")
                now_in_iran = timezone.now().astimezone(iran_tz)
                gregorian_date_naive = python_datetime.combine(submitted_jalali_date.togregorian(), now_in_iran.time())
                submission_datetime_aware_iran = iran_tz.localize(gregorian_date_naive)
                submission_datetime_aware_utc = submission_datetime_aware_iran.astimezone(pytz.utc)

            except Exception as e:
                print(e)
                messages.error(request, "خطا در پردازش تاریخ و زمان. لطفاً مجدداً تلاش کنید.")
                return response

            try:
                submitted_date_gregorian = submitted_jalali_date.togregorian()
                existing_target_today = Target.objects.filter(
                    user=user_instance,
                    submission_date__date=submitted_date_gregorian
                )
                if existing_target_today.exists():
                    messages.warning(request, "شما قبلاً هدف خود را برای این تاریخ ثبت کرده‌اید.")
                    return response
            except Exception as e:
                print(e)
                messages.error(request, "خطا در بررسی هدف قبلی. لطفاً مجدداً تلاش کنید.")
                return response

            try:
                Target.objects.create(
                    user=user_instance,
                    content=target_content,
                    submission_date=submission_datetime_aware_utc
                )
                # TODO: اگر اسکریپت ارسال به گروه به این منطق جدید نیاز دارد، آن را در اینجا یا پس از آن تغییر دهید.
                res = run_send_to_group_script.delay()
                messages.success(request, "هدف شما با موفقیت ثبت شد.")
            except IntegrityError:
                messages.warning(request, "شما قبلاً هدفی برای این تاریخ ثبت کرده‌اید.")
            except Exception as e:
                print(e)
                messages.error(request, "خطا در ثبت هدف. لطفاً مجدداً تلاش کنید.")

        return response


    # GET request
    elif request.method == "GET":
        hardcoded_names = []
        dates = []
        now_jalali = utils.get_jalali_date_time()

        # *** منطق اصلی تغییر یافته:
        # اگر کاربر لاگین نیست و در گروه تولیدی هم نیست، لیست تمام اسامی را نمایش بده
        # اگر کاربر لاگین نیست و در گروه تولیدی است (این حالت نباید اتفاق بیفتد اگر منطق ما درست باشد،
        # اما برای اطمینان): او را به صفحه لاگین ریدایرکت کن.
        # اگر کاربر لاگین است و در گروه تولیدی است: فقط نام خودش را نمایش بده.
        # اگر کاربر لاگین است ولی در گروه تولیدی نیست: لیست تمام اسامی را نمایش بده (می‌توانید این را هم به نام خودش محدود کنید).

        if request.user.is_authenticated:
            if user_can_access_project_form:
                # کاربر لاگین است و عضو گروه Production یا Project_Management است.
                # فقط نام خودش را در لیست قرار بده.
                hardcoded_names = [request.user.get_full_name()]
            else:
                # کاربر لاگین است ولی عضو گروه Production یا Project_Management نیست.
                # می‌تواند اهداف عمومی ثبت کند، پس لیست تمام اسامی را می‌بیند (اختیاری: فقط نام خودش).
                hardcoded_names = CustomUser.objects.filter(
                    access_level__gt=0,
                ).annotate(
                    full_name=Concat(F("first_name"), Value(" "), F("last_name")),
                ).exclude(
                    Q(is_active=False)
                ).values_list('full_name', flat=True).distinct()
        else: # کاربر لاگین نیست
            # لیست اسامی تمام کاربرانی که مسئولیت تولیدی ندارند را نمایش بده.
            # کاربرانی که مسئولیت تولیدی دارند (یعنی باید لاگین کنند تا فرم ویژه را ببینند)
            # از این لیست حذف می‌شوند تا بدون لاگین اسمشان دیده نشود.
            production_group_users_ids = CustomUser.objects.filter(
                groups__name__in=allowed_groups
            ).values_list('id', flat=True)

            hardcoded_names = CustomUser.objects.filter(
                access_level__gt=0,
            ).exclude(
                Q(is_active=False) | Q(id__in=production_group_users_ids)
            ).annotate(
                full_name=Concat(F("first_name"), Value(" "), F("last_name")),
            ).values_list('full_name', flat=True).distinct()
            
            # اگر کاربر لاگین نیست و تلاش می‌کند به فرم پروژه دسترسی پیدا کند،
            # این وضعیت توسط 'user_can_access_project_form' کنترل می‌شود که در این حالت False است
            # و فرم پروژه اصلا نمایش داده نمی‌شود.


        dates.append(now_jalali)
        if now_jalali.hour < 14 and request.user.is_authenticated:
            yesterday_jalali = now_jalali - timedelta(days=1)
            yesterday_gregorian = yesterday_jalali.togregorian().date()
            if not Target.objects.filter(user=request.user, submission_date__date=yesterday_gregorian).exists():
                dates.append(yesterday_jalali)

        projects = None
        if request.user.is_authenticated and user_can_access_project_form:
            projects = Project.objects.filter(
                production_orders__assigned_to__in=request.user.groups.all(),
                production_orders__status__in=[ProductionOrder.StatusChoices.PENDING, ProductionOrder.StatusChoices.IN_PROGRESS]
            ).distinct().order_by('name')


        target_text = parse.unquote(request.COOKIES.get("target_text", ""))
        context = {
            'hardcoded_names': hardcoded_names,
            "dates": dates,
            "target_text": target_text,
            "projects": projects,
            "user_can_access_project_form": user_can_access_project_form
        }
        return render(request, 'targets/submit_target.html', context)
    return None


@login_required
def get_project_fields_view(request, project_id):
    """
    این ویو یک قطعه HTML شامل فیلدهای سفارشات تولید مرتبط با یک پروژه را برمی‌گرداند.
    """
    try:
        project = Project.objects.get(id=project_id)
        # یافتن سفارشات تولید فعال (PENDING یا IN_PROGRESS) برای این پروژه
        production_orders = ProductionOrder.objects.filter(
            project=project,
            status__in=['PENDING', 'IN_PROGRESS']
        ).prefetch_related('product').order_by('created_at')

        context = {
            'project': project,
            'production_orders': production_orders, # ارسال ProductionOrder ها به جای Product ها
        }
        # رندر کردن یک تمپلیت جزئی (partial)
        return render(request, 'targets/partials/_project_fields.html', context)
    except Project.DoesNotExist:
        return HttpResponseNotFound("Project not found.")
    except Exception as e:
        # برای اشکال‌زدایی بهتر
        print(f"Error in get_project_fields_view: {e}")
        return JsonResponse({"error": "An error occurred"}, status=500)


@login_required
@user_passes_test(test_func=lambda x: x.id in [61, 55, 1])
@csrf_exempt
@require_POST
def send_targets_to_igap(request):
    try:
        res = run_send_to_group_script.delay()
        return JsonResponse({"status": "ok", "message": f"اهداف با موفقیت ارسال شدند!"})
    except Exception as e:
        print(e)
        return JsonResponse({"status": "error", "message": f"خطای سرور، لطفا با توسعه دهنده وبسایت در میان بگذارید!"}, status=500)


@shared_task
def run_send_to_group_script():
    result = subprocess.run(
        ["/home/amirz/fccc_targets/.venv/bin/python", "send_targets_igap_group/push_targets_with_date.py"],
        capture_output=True,
        text=True
    )

    print(">>> Script stdout:\n", result.stdout)
    print(">>> Script stderr:\n", result.stderr)

    return {
        "returncode": result.returncode,
    }