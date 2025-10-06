from django.apps import AppConfig


class ColetaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.coleta'

    def ready(self):
        """Importa signals quando app estiver pronto."""
        import apps.coleta.signals  # noqa
