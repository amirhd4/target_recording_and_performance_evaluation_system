from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fccc_targets.settings')

app = Celery('fccc_targets')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()