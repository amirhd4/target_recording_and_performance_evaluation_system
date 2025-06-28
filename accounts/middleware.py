from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
import secrets # برای مقایسه امن توکن‌ها
import json # برای پاسخ JSON


class UnderConstructionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # آدرس صفحه‌ای که کاربر باید بهش هدایت بشه
        under_construction_path = reverse('under_construction')

        # لیست مسیرهایی که نباید redirect بشن (مثلاً صفحه لاگین یا خود under_construction)
        excluded_paths = [
            reverse('login'), 
            under_construction_path,
            '/admin/login/', '/admin/', "/logout/", 
        ]
        # "/api/monthly_scores_summary/", "/targets/submit_target/"
        # بررسی اینکه مسیر فعلی جزو مسیرهای مستثنا نباشه
        # if not request.path.startswith(tuple(excluded_paths)):
        #     # print(request.META.get("HTTP_X_FORWARDED_FOR"))
        #     # شرط اصلی ما: اگه کاربر لاگین نکرده یا شرط خاصی نداشت
        #     if request.user.is_authenticated:
        #         # request.META.get("HTTP_X_FORWARDED_FOR") != "192.168.2.163"
        #         # not(request.user.id in [61, 15, 1, 30]) or
        #         if  request.META.get("HTTP_X_FORWARDED_FOR") != "192.168.2.134":
        #             return redirect(under_construction_path)

        return self.get_response(request)


class ProjectStaticTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # شما می‌توانید لیست مسیرهای محافظت شده و توکن را در زمان اولیه سازی بخوانید
        # تا در هر درخواست دوباره خوانده نشوند
        self.protected_paths = settings.STATIC_TOKEN_REQUIRED_PATHS
        self.expected_token = settings.PROJECT_API_KEY_ENV_VAR


    def __call__(self, request):
        # منطق بررسی احراز هویت قبل از رفتن به View

        # بررسی می‌کنیم آیا مسیر فعلی درخواست در لیست مسیرهای محافظت شده است یا خیر
        # request.path_info شامل مسیر بدون دامنه و با / اول است (مثلاً /api/protected-endpoint/)
        is_protected_path = request.path_info in self.protected_paths

        if is_protected_path:
            # اگر مسیر محافظت شده است، توکن را در هدر Authorization جستجو می‌کنیم
            auth_header = request.headers.get('Authorization') # نام هدر معمولا Authorization است

            if not auth_header:
                # اگر هدر Authorization وجود نداشت، دسترسی ممنوع است
                return self.get_forbidden_response("هدر Authorization یافت نشد.")

            # هدر را به دو قسمت جدا می‌کنیم (انتظار داریم "Api-Key توکن_شما" باشد)
            parts = auth_header.split()

            if len(parts) != 2 or parts[0].lower() != 'api-key':
                # اگر فرمت هدر درست نبود
                 return self.get_forbidden_response('فرمت هدر Authorization باید "Api-Key <token>" باشد.')

            provided_token = parts[1] # توکن ارسالی از سرویس سرویس‌گیرنده

            # مقایسه امن توکن ارسالی با توکن مورد انتظار از تنظیمات
            # از secrets.compare_digest برای جلوگیری از حملات زمان‌بندی استفاده کنید
            is_valid = secrets.compare_digest(provided_token, self.expected_token)

            if not is_valid:
                # اگر توکن‌ها تطابق نداشتند، دسترسی ممنوع است
                return self.get_forbidden_response("کلید API پروژه نامعتبر است.")

            # اگر توکن معتبر بود، درخواست می‌تواند ادامه یابد و به View برسد
            # در اینجا می‌توانید اطلاعات احراز هویت (مثلاً یک کاربر 'سرویس' مجازی) را
            # به شیء request اضافه کنید اگر View به آن نیاز داشته باشد
            # request.is_authenticated_with_static_token = True # مثال

        # اگر مسیر محافظت شده نبود یا توکن معتبر بود، درخواست به میان‌افزارهای بعدی یا View ارسال می‌شود
        response = self.get_response(request)

        # منطق پردازش پاسخ بعد از View (اگر لازم باشد)
        return response

    def get_forbidden_response(self, error_message):
        """یک پاسخ 403 Forbidden با پیام خطا برمی‌گرداند."""
        # می‌توانید پاسخ JSON برگردانید که برای APIها رایج‌تر است
        response_data = {"error": error_message, "code": "permission_denied"}
        return JsonResponse(response_data, status=403)

        # یا فقط یک پاسخ HTTP ساده
        # return HttpResponseForbidden(error_message)
