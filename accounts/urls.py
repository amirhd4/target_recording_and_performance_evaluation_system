from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from accounts.forms import PersianPasswordChangeForm


# HANDLER403 = 'accounts.views.custom_view_403'


urlpatterns = [
    path('login/', views.user_login_view, name='login'),
    path("logout/", views.logout_view, name="logout"),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='dashboard'),
    path('update_monthly_scores/', views.update_monthly_scores, name='update_monthly_scores'),
    path('submit_daily_score/', views.submit_daily_score, name='submit_daily_score'),
    path('submit_past_daily_score/', views.submit_daily_score, name='submit_past_daily_score'),
    # **URL تغییر رمز عبور - استفاده از فرم سفارشی**
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='accounts/password_change_form.html', form_class=PersianPasswordChangeForm), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'), name='password_change_done'),
    path('under_construction/', views.under_construction, name='under_construction'),
    path("knowledge_management/", views.knowledge_management, name="knowledge_management"),
    path('my_responsibilities/', views.user_responsibilities_view, name='user_responsibilities'),
    path("user_monthly_performance", views.user_monthly_performance, name="user_monthly_performance"),
    # path('knowledge_management/delete/<int:entry_id>/', views.delete_knowledge_management_entry_view, name='delete_km_entry'),
    # path('knowledge_management/edit/<int:entry_id>/', views.edit_knowledge_management_entry_view, name='edit_km_entry'),
    path('my_responsibilities/', views.user_responsibilities_view, name='user_responsibilities'),
    path('regulations/toggle-read/', views.toggle_regulation_read_status, name='toggle_regulation_read'),
    path('regulations/confirm-all/', views.confirm_all_regulations_read, name='confirm_all_regulations'),
    path('media/<int:user_id>/<path:path>/', views.protected_media_view, name='media'),
    path('media/regulations/<path:path>', views.protected_media_view_req, name='media_reg'),
]
