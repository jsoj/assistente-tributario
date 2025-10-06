"""
Management command para executar scrapers manualmente.

Uso:
    python manage.py executar_scraper <fonte_nome>
    python manage.py executar_scraper --todos
    python manage.py executar_scraper --criar-fonte-exemplo
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.coleta.models import FonteDados
from apps.coleta.scrapers import CositScraper
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa scraper para uma fonte específica'

    def add_arguments(self, parser):
        parser.add_argument(
            'fonte_nome',
            nargs='?',
            type=str,
            help='Nome da fonte de dados a ser coletada'
        )

        parser.add_argument(
            '--todos',
            action='store_true',
            help='Executa scrapers de todas as fontes ativas'
        )

        parser.add_argument(
            '--criar-fonte-exemplo',
            action='store_true',
            help='Cria fonte de dados de exemplo para COSIT'
        )

    def handle(self, *args, **options):
        """Processa comando."""

        # Criar fonte de exemplo
        if options['criar_fonte_exemplo']:
            self._criar_fonte_cosit()
            return

        # Executar todos os scrapers
        if options['todos']:
            self._executar_todos()
            return

        # Executar scraper específico
        fonte_nome = options.get('fonte_nome')
        if not fonte_nome:
            raise CommandError(
                'Forneça o nome da fonte ou use --todos. '
                'Use --criar-fonte-exemplo para criar fonte de teste.'
            )

        self._executar_fonte(fonte_nome)

    def _criar_fonte_cosit(self):
        """Cria fonte de dados de exemplo para COSIT."""
        self.stdout.write(self.style.WARNING('Criando fonte de dados COSIT...'))

        fonte, criada = FonteDados.objects.get_or_create(
            nome='COSIT - Soluções de Consulta',
            defaults={
                'descricao': 'Soluções de Consulta publicadas pela Coordenação-Geral de Tributação (COSIT) da Receita Federal',
                'tipo': 'web',
                'url_base': 'https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/solucoes-de-consulta',
                'frequencia_coleta': 'semanal',
                'scraper_class': 'CositScraper',
                'status': 'ativo',
                'ativo': True
            }
        )

        if criada:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Fonte criada: {fonte.nome}')
            )
            self.stdout.write(
                f'  ID: {fonte.id}\n'
                f'  URL: {fonte.url_base}\n'
                f'  Scraper: {fonte.scraper_class}'
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠ Fonte já existe: {fonte.nome}')
            )

        self.stdout.write(
            '\nPara executar a coleta:\n'
            f'  python manage.py executar_scraper "{fonte.nome}"\n'
        )

    def _executar_todos(self):
        """Executa scrapers de todas as fontes ativas."""
        fontes = FonteDados.objects.filter(ativo=True, status='ativo')

        if not fontes.exists():
            self.stdout.write(
                self.style.WARNING('Nenhuma fonte ativa encontrada.')
            )
            self.stdout.write(
                'Use --criar-fonte-exemplo para criar uma fonte de teste.'
            )
            return

        self.stdout.write(
            self.style.WARNING(f'Executando {fontes.count()} fonte(s) ativa(s)...\n')
        )

        sucesso_total = 0
        erro_total = 0

        for fonte in fontes:
            try:
                sucesso = self._executar_fonte(fonte.nome)
                if sucesso:
                    sucesso_total += 1
                else:
                    erro_total += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Erro ao executar {fonte.nome}: {e}')
                )
                erro_total += 1

        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(f'✓ Sucesso: {sucesso_total}') + ' | ' +
            self.style.ERROR(f'✗ Erro: {erro_total}')
        )

    def _executar_fonte(self, fonte_nome: str) -> bool:
        """
        Executa scraper de uma fonte específica.

        Args:
            fonte_nome: Nome da fonte

        Returns:
            True se sucesso, False se erro
        """
        try:
            # Buscar fonte
            try:
                fonte = FonteDados.objects.get(nome=fonte_nome)
            except FonteDados.DoesNotExist:
                raise CommandError(
                    f'Fonte "{fonte_nome}" não encontrada. '
                    f'Use --criar-fonte-exemplo para criar uma fonte de teste.'
                )

            # Verificar se está ativa
            if not fonte.ativo:
                raise CommandError(f'Fonte "{fonte_nome}" está inativa')

            # Obter classe do scraper
            scraper_class = self._obter_scraper_class(fonte.scraper_class)

            # Informações iniciais
            self.stdout.write('='*60)
            self.stdout.write(
                self.style.MIGRATE_HEADING(f'Executando: {fonte.nome}')
            )
            self.stdout.write(f'URL: {fonte.url_base}')
            self.stdout.write(f'Scraper: {fonte.scraper_class}')
            self.stdout.write(f'Última coleta: {fonte.ultima_coleta or "Nunca"}')
            self.stdout.write('-'*60)

            # Instanciar e executar scraper
            scraper = scraper_class(fonte)
            sucesso = scraper.executar()

            # Resultado
            if sucesso:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ Coleta concluída com sucesso!')
                )
                self.stdout.write(
                    f'  Novos: {scraper.docs_novos}\n'
                    f'  Atualizados: {scraper.docs_atualizados}\n'
                    f'  Ignorados: {scraper.docs_ignorados}\n'
                    f'  Erros: {scraper.docs_erro}'
                )

                # Mostrar último log
                if scraper.log:
                    self.stdout.write(
                        f'\n  Log ID: {scraper.log.id}\n'
                        f'  Duração: {scraper.log.duracao_segundos}s\n'
                        f'  Status: {scraper.log.status}'
                    )

                return True
            else:
                self.stdout.write(
                    self.style.ERROR(f'\n✗ Coleta falhou')
                )
                if scraper.log:
                    self.stdout.write(f'  Mensagem: {scraper.log.mensagem}')
                    if scraper.log.erro_detalhe:
                        self.stdout.write(f'  Erro: {scraper.log.erro_detalhe}')
                return False

        except CommandError:
            raise
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Erro fatal: {e}')
            )
            logger.exception(f'Erro ao executar scraper {fonte_nome}')
            return False

    def _obter_scraper_class(self, nome_classe: str):
        """
        Obtém classe do scraper pelo nome.

        Args:
            nome_classe: Nome da classe (ex: 'CositScraper')

        Returns:
            Classe do scraper

        Raises:
            CommandError se classe não encontrada
        """
        # Mapeamento de scrapers disponíveis
        scrapers_disponiveis = {
            'CositScraper': CositScraper,
            # Adicionar novos scrapers aqui
        }

        if nome_classe not in scrapers_disponiveis:
            raise CommandError(
                f'Scraper "{nome_classe}" não implementado. '
                f'Disponíveis: {", ".join(scrapers_disponiveis.keys())}'
            )

        return scrapers_disponiveis[nome_classe]
