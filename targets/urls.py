from django.urls import path
from . import views # وارد کردن view های اپلیکیشن Targets

urlpatterns = [
    path('submit_target/', views.submit_target_view, name='submit_target'),
    path('send_to_igap_group/', views.send_targets_to_igap, name='send_to_igap_group'),
    path('get_project_fields/<int:project_id>/', views.get_project_fields_view, name='get_project_fields'),

]