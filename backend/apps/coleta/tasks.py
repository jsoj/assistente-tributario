"""
Celery tasks para coleta automatizada de dados.

Tasks que podem ser agendadas via Celery Beat para executar
scrapers periodicamente conforme configuração de cada fonte.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import FonteDados, LogColeta
from .scrapers import CositScraper

logger = logging.getLogger(__name__)


# Mapeamento de scrapers disponíveis
SCRAPERS_DISPONIVEIS = {
    'CositScraper': CositScraper,
    # Adicionar novos scrapers aqui
}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def executar_scraper_fonte(self, fonte_id: int) -> dict:
    """
    Executa scraper de uma fonte específica.

    Args:
        fonte_id: ID da fonte de dados

    Returns:
        Dict com resultados da execução
    """
    try:
        # Buscar fonte
        try:
            fonte = FonteDados.objects.get(id=fonte_id, ativo=True)
        except FonteDados.DoesNotExist:
            logger.error(f"Fonte {fonte_id} não encontrada ou inativa")
            return {
                'sucesso': False,
                'erro': 'Fonte não encontrada ou inativa'
            }

        logger.info(f"Iniciando coleta para fonte {fonte.nome} (ID: {fonte_id})")

        # Obter classe do scraper
        scraper_class_name = fonte.scraper_class
        if scraper_class_name not in SCRAPERS_DISPONIVEIS:
            logger.error(f"Scraper {scraper_class_name} não implementado")
            return {
                'sucesso': False,
                'erro': f'Scraper {scraper_class_name} não implementado'
            }

        scraper_class = SCRAPERS_DISPONIVEIS[scraper_class_name]

        # Instanciar e executar scraper
        scraper = scraper_class(fonte)
        sucesso = scraper.executar()

        # Resultado
        resultado = {
            'sucesso': sucesso,
            'fonte_id': fonte_id,
            'fonte_nome': fonte.nome,
            'novos': scraper.docs_novos,
            'atualizados': scraper.docs_atualizados,
            'ignorados': scraper.docs_ignorados,
            'erros': scraper.docs_erro,
            'log_id': scraper.log.id if scraper.log else None
        }

        if not sucesso:
            resultado['mensagem'] = scraper.log.mensagem if scraper.log else 'Erro desconhecido'

        logger.info(
            f"Coleta finalizada para {fonte.nome}: "
            f"Novos={scraper.docs_novos}, "
            f"Atualizados={scraper.docs_atualizados}, "
            f"Erros={scraper.docs_erro}"
        )

        return resultado

    except Exception as e:
        logger.exception(f"Erro ao executar scraper para fonte {fonte_id}: {e}")

        # Tentar novamente em caso de erro de rede
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                'sucesso': False,
                'fonte_id': fonte_id,
                'erro': f'Máximo de tentativas excedido: {str(e)}'
            }


@shared_task
def executar_todas_fontes_ativas() -> dict:
    """
    Executa scrapers de todas as fontes ativas que estão no horário.

    Verifica campo 'proxima_coleta' e executa apenas fontes que
    estão prontas para serem coletadas.

    Returns:
        Dict com estatísticas de execução
    """
    logger.info("Iniciando execução de todas as fontes ativas")

    agora = timezone.now()

    # Buscar fontes ativas que estão prontas para coleta
    fontes = FonteDados.objects.filter(
        ativo=True,
        status='ativo'
    ).filter(
        # Coletar se proxima_coleta é None ou já passou
        models.Q(proxima_coleta__isnull=True) |
        models.Q(proxima_coleta__lte=agora)
    )

    total = fontes.count()
    logger.info(f"Encontradas {total} fonte(s) pronta(s) para coleta")

    if total == 0:
        return {
            'total': 0,
            'executadas': 0,
            'sucesso': 0,
            'erro': 0
        }

    # Executar cada fonte
    resultados = {
        'total': total,
        'executadas': 0,
        'sucesso': 0,
        'erro': 0,
        'detalhes': []
    }

    for fonte in fontes:
        try:
            # Executar de forma assíncrona
            resultado = executar_scraper_fonte.apply_async(
                args=[fonte.id],
                countdown=0
            )

            resultados['executadas'] += 1
            resultados['detalhes'].append({
                'fonte_id': fonte.id,
                'fonte_nome': fonte.nome,
                'task_id': resultado.id
            })

            logger.info(f"Task criada para {fonte.nome}: {resultado.id}")

        except Exception as e:
            logger.error(f"Erro ao criar task para {fonte.nome}: {e}")
            resultados['erro'] += 1

    return resultados


@shared_task
def calcular_proxima_coleta(fonte_id: int):
    """
    Calcula e atualiza campo 'proxima_coleta' com base na frequência.

    Args:
        fonte_id: ID da fonte de dados
    """
    try:
        fonte = FonteDados.objects.get(id=fonte_id)

        # Mapeamento de frequências para timedelta
        frequencias = {
            'horaria': timedelta(hours=1),
            'diaria': timedelta(days=1),
            'semanal': timedelta(weeks=1),
            'mensal': timedelta(days=30),
        }

        delta = frequencias.get(fonte.frequencia_coleta, timedelta(days=1))
        fonte.proxima_coleta = timezone.now() + delta
        fonte.save(update_fields=['proxima_coleta'])

        logger.info(
            f"Próxima coleta para {fonte.nome} agendada para {fonte.proxima_coleta}"
        )

    except FonteDados.DoesNotExist:
        logger.error(f"Fonte {fonte_id} não encontrada")
    except Exception as e:
        logger.error(f"Erro ao calcular próxima coleta: {e}")


@shared_task
def limpar_logs_antigos(dias: int = 90):
    """
    Remove logs de coleta mais antigos que X dias.

    Args:
        dias: Número de dias para manter logs (padrão: 90)
    """
    try:
        data_limite = timezone.now() - timedelta(days=dias)

        logs_deletados, _ = LogColeta.objects.filter(
            iniciado_em__lt=data_limite
        ).delete()

        logger.info(f"Removidos {logs_deletados} logs com mais de {dias} dias")

        return {
            'sucesso': True,
            'logs_deletados': logs_deletados,
            'dias': dias
        }

    except Exception as e:
        logger.error(f"Erro ao limpar logs antigos: {e}")
        return {
            'sucesso': False,
            'erro': str(e)
        }


# Importação necessária para executar_todas_fontes_ativas
from django.db import models
