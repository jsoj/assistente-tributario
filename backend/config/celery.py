"""
Celery configuration for assistente-tributario project.

Configura Celery para processamento assíncrono de tasks,
incluindo agendamento de scrapers via Celery Beat.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('assistente_tributario')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Configuração do Celery Beat para agendamento periódico
app.conf.beat_schedule = {
    # Executar todas as fontes ativas a cada 6 horas
    'executar-todas-fontes-6h': {
        'task': 'apps.coleta.tasks.executar_todas_fontes_ativas',
        'schedule': crontab(minute=0, hour='*/6'),  # 00:00, 06:00, 12:00, 18:00
        'options': {
            'expires': 3600,  # Expira em 1 hora se não executar
        }
    },

    # Limpar logs antigos semanalmente (domingo às 3h da manhã)
    'limpar-logs-antigos': {
        'task': 'apps.coleta.tasks.limpar_logs_antigos',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),
        'kwargs': {'dias': 90},
    },
}

# Timezone para Celery Beat
app.conf.timezone = 'America/Sao_Paulo'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
