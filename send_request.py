from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
import json
import requests

def req():
	# ... کدهای مربوط به توکن و هدرها ...
	AUTH_TOKEN = "8226bbace2280f87af6c190e10db4d9147186e49"
	auth_header_value = f'Token {AUTH_TOKEN}'

	headers = {
		'Authorization': auth_header_value,
		'Accept': 'application/json',
	}

	BASE_URL = "http://192.168.2.105:8000"
	# API_PATH = "/api/users_monthly_scores/"
	# API_PATH = "/api/users_daily_scores/"
	API_PATH = "/api/targets/"
	FULL_URL = f"{BASE_URL}{API_PATH}"

	# تعیین Timeout برای درخواست (مثلا 10 ثانیه)
	request_timeout = 25 # ثانیه
	print(f"Sending GET request to: {FULL_URL} with timeout {request_timeout}s")
	print(f"Authorization header: {headers['Authorization']}")

	try:
		# ارسال درخواست با تعیین timeout
		response = requests.get(FULL_URL, headers=headers, timeout=request_timeout)

		# بررسی کد وضعیت HTTP (خطاها را به Exception تبدیل می‌کند)
		response.raise_for_status()

		print(f"Request successful! Status Code: {response.status_code}")

		# دریافت و برگرداندن پاسخ JSON
		try:
			response_data = response.json()
			# می‌توانید این داده را به Context قالب خود اضافه کنید یا به هر نحو دیگری استفاده کنید
			# در اینجا برای مثال، آن را به عنوان پاسخ JSON برمی‌گردانیم (ممکن است بخواهید این را در قالب رندر کنید)
			# return JsonResponse(response_data, status=response.status_code)
			# برای نمایش در قالب، باید داده را در Context قرار دهید
			print("Received data from external API.")
			print(response_data)
			# return response_data # یا هر پردازش دیگری روی داده

		except json.JSONDecodeError:
			print("Warning: Received non-JSON response from external API.")
			# مدیریت پاسخ غیر JSON
			# return HttpResponseServerError("Received invalid response format from internal API.")
			return {"error": "Invalid response format from internal API", "status": response.status_code, "body": response.text} # یا هر فرمت خطای دیگر

	except requests.exceptions.Timeout:
		# مدیریت خطای Timeout
		print(f"Request to internal API timed out after {request_timeout} seconds.")
		# return HttpResponseServerError(f"Request to internal API timed out.")
		return {"error": f"Request to internal API timed out after {request_timeout} seconds."}

	except requests.exceptions.RequestException as e:
		# مدیریت سایر خطاهای requests (اتصال، 401, 403, ...)
		print(f"Error communicating with internal API: {e}")
		status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
		error_body = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
		# return HttpResponseServerError(f"Error communicating with internal API: {status_code or ''} {e}")
		return {"error": "Error communicating with internal API", "status": status_code, "details": error_body}

	except Exception as e:
		print(f"An unexpected error occurred during API call: {e}")
		# return HttpResponseServerError("An unexpected error occurred.")
		return {"error": "An unexpected error occurred during API call"}


req()