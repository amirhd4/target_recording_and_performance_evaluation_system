from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api import views as api_views
from .views import (
    MonthlyScoreViewSetNew, TargetViewSetNew, DailyScoreViewSetNew,
)

router = DefaultRouter()
# router.register(r"monthlyscores", MonthlyScoreViewSetNew, basename="monthlyscores")
router.register(r"targets", TargetViewSetNew, basename="targets")
router.register(r"dailyscores", DailyScoreViewSetNew, basename="dailyscores")


urlpatterns = [
    # path('monthly_scores_summary', api_views.monthly_scores_summary, name='monthly_scores_summary'),
    # path("monthly_scores_summary_excel", api_views.monthly_scores_summary_excel, name="monthly_scores_summary_excel"),
    path('', include(router.urls)),
]