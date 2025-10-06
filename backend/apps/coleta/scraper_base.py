"""
Classe base para todos os scrapers (Bloco 1 - Coleta).

Fornece funcionalidades comuns para coleta de dados de fontes
governamentais, incluindo rate limiting, detecção de mudanças,
e persistência de dados.
"""
import logging
import time
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import requests
from bs4 import BeautifulSoup

from .models import FonteDados, DocumentoFonte, LogColeta

logger = logging.getLogger(__name__)


class ScraperBase(ABC):
    """
    Classe base abstrata para scrapers.

    Todos os scrapers devem herdar desta classe e implementar
    os métodos abstratos.
    """

    def __init__(self, fonte: FonteDados):
        """
        Inicializa o scraper.

        Args:
            fonte: Instância do model FonteDados configurado
        """
        self.fonte = fonte
        self.log = None
        self.session = requests.Session()
        self._configurar_session()

        # Estatísticas
        self.docs_novos = 0
        self.docs_atualizados = 0
        self.docs_ignorados = 0
        self.docs_erro = 0

    def _configurar_session(self):
        """Configura a sessão HTTP com headers adequados."""
        user_agent = getattr(
            settings,
            'SCRAPER_USER_AGENT',
            'AssistenteTributario/1.0 (Educational)'
        )
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    def _delay(self):
        """
        Implementa rate limiting entre requisições.

        Usa delay configurável para ser respeitoso com servidores.
        """
        delay_min = getattr(settings, 'SCRAPER_DELAY_MIN', 1)
        delay_max = getattr(settings, 'SCRAPER_DELAY_MAX', 3)
        time.sleep(random.uniform(delay_min, delay_max))

    def _criar_log(self) -> LogColeta:
        """Cria registro de log para esta execução."""
        self.log = LogColeta.objects.create(
            fonte=self.fonte,
            status='iniciado',
            iniciado_em=timezone.now()
        )
        logger.info(f"Iniciando coleta para {self.fonte.nome} (LogID: {self.log.id})")
        return self.log

    def _finalizar_log(self, status: str, mensagem: str = '', erro: str = ''):
        """
        Finaliza o log de execução.

        Args:
            status: 'sucesso', 'erro', ou 'cancelado'
            mensagem: Mensagem descritiva
            erro: Detalhes do erro (se houver)
        """
        if not self.log:
            return

        self.log.status = status
        self.log.finalizado_em = timezone.now()
        self.log.calcular_duracao()

        self.log.documentos_novos = self.docs_novos
        self.log.documentos_atualizados = self.docs_atualizados
        self.log.documentos_ignorados = self.docs_ignorados
        self.log.documentos_erro = self.docs_erro

        self.log.mensagem = mensagem
        self.log.erro_detalhe = erro
        self.log.save()

        # Atualizar fonte
        self.fonte.ultima_coleta = timezone.now()
        self.fonte.save()

        logger.info(
            f"Coleta finalizada: {status} | "
            f"Novos: {self.docs_novos}, "
            f"Atualizados: {self.docs_atualizados}, "
            f"Ignorados: {self.docs_ignorados}, "
            f"Erros: {self.docs_erro}"
        )

    def _obter_caminho_arquivo(self, identificador: str, extensao: str = 'html') -> Path:
        """
        Gera caminho para salvar arquivo bruto.

        Args:
            identificador: ID único do documento
            extensao: Extensão do arquivo (html, pdf, json, etc.)

        Returns:
            Path object do arquivo
        """
        # Estrutura: /data/raw/{fonte_nome}/{ano}/{mes}/{identificador}.{ext}
        data_dir = Path(settings.BASE_DIR).parent / 'data' / 'raw'
        fonte_dir = data_dir / self.fonte.nome.lower().replace(' ', '_')

        # Organizar por data
        agora = datetime.now()
        ano_mes_dir = fonte_dir / str(agora.year) / f"{agora.month:02d}"
        ano_mes_dir.mkdir(parents=True, exist_ok=True)

        # Sanitizar identificador
        safe_id = identificador.replace('/', '_').replace('\\', '_')
        return ano_mes_dir / f"{safe_id}.{extensao}"

    def _salvar_documento(
        self,
        titulo: str,
        conteudo: str,
        url: str,
        identificador: str,
        tipo_documento: str = 'outro',
        metadados: Optional[Dict[str, Any]] = None
    ) -> Optional[DocumentoFonte]:
        """
        Salva um documento coletado.

        Verifica se já existe (via hash) e atualiza se necessário.

        Args:
            titulo: Título do documento
            conteudo: Conteúdo bruto (HTML, texto, etc.)
            url: URL de origem
            identificador: ID único no site de origem
            tipo_documento: Tipo (lei, consulta, etc.)
            metadados: Dict com metadados adicionais

        Returns:
            Instância de DocumentoFonte criada ou atualizada
        """
        try:
            # Calcular hash do conteúdo
            hash_atual = DocumentoFonte.calcular_hash(conteudo)

            # Verificar se documento já existe
            try:
                doc_existente = DocumentoFonte.objects.get(
                    fonte=self.fonte,
                    identificador_externo=identificador
                )

                # Verificar se conteúdo mudou
                if doc_existente.hash_conteudo == hash_atual:
                    self.docs_ignorados += 1
                    logger.debug(f"Documento ignorado (sem mudanças): {identificador}")
                    return doc_existente

                # Conteúdo mudou - atualizar
                doc_existente.hash_conteudo = hash_atual
                doc_existente.versao += 1
                doc_existente.titulo = titulo
                doc_existente.url_origem = url
                doc_existente.status = 'coletado'

                # Atualizar metadados se fornecidos
                if metadados:
                    if 'data_publicacao' in metadados:
                        doc_existente.data_publicacao = metadados['data_publicacao']
                    if 'orgao_emissor' in metadados:
                        doc_existente.orgao_emissor = metadados['orgao_emissor']
                    if 'numero_documento' in metadados:
                        doc_existente.numero_documento = metadados['numero_documento']

                doc_existente.save()
                self.docs_atualizados += 1
                logger.info(f"Documento atualizado: {identificador} (v{doc_existente.versao})")

                # Salvar arquivo atualizado
                caminho = self._obter_caminho_arquivo(identificador, 'html')
                caminho.write_text(conteudo, encoding='utf-8')
                doc_existente.caminho_arquivo = str(caminho.relative_to(Path(settings.BASE_DIR).parent))
                doc_existente.tamanho_bytes = len(conteudo.encode('utf-8'))
                doc_existente.save()

                return doc_existente

            except DocumentoFonte.DoesNotExist:
                # Documento novo
                caminho = self._obter_caminho_arquivo(identificador, 'html')
                caminho.write_text(conteudo, encoding='utf-8')

                doc_novo = DocumentoFonte.objects.create(
                    fonte=self.fonte,
                    titulo=titulo,
                    tipo_documento=tipo_documento,
                    url_origem=url,
                    identificador_externo=identificador,
                    hash_conteudo=hash_atual,
                    caminho_arquivo=str(caminho.relative_to(Path(settings.BASE_DIR).parent)),
                    tamanho_bytes=len(conteudo.encode('utf-8')),
                    data_publicacao=metadados.get('data_publicacao') if metadados else None,
                    orgao_emissor=metadados.get('orgao_emissor', '') if metadados else '',
                    numero_documento=metadados.get('numero_documento', '') if metadados else '',
                )

                self.docs_novos += 1
                logger.info(f"Documento novo salvo: {identificador}")
                return doc_novo

        except Exception as e:
            self.docs_erro += 1
            logger.error(f"Erro ao salvar documento {identificador}: {e}", exc_info=True)
            return None

    # Métodos abstratos que devem ser implementados por cada scraper

    @abstractmethod
    def coletar(self) -> bool:
        """
        Método principal de coleta.

        Deve ser implementado por cada scraper específico.
        Retorna True se a coleta foi bem-sucedida, False caso contrário.
        """
        pass

    @abstractmethod
    def validar_configuracao(self) -> bool:
        """
        Valida se a configuração do scraper está correta.

        Retorna True se válida, False caso contrário.
        """
        pass

    # Método público para executar o scraper

    def executar(self) -> bool:
        """
        Executa o scraper completo.

        Este é o método que deve ser chamado externamente.
        Gerencia log, exceções e finalização.

        Returns:
            True se sucesso, False se erro
        """
        try:
            # Validar configuração
            if not self.validar_configuracao():
                logger.error(f"Configuração inválida para {self.fonte.nome}")
                return False

            # Criar log
            self._criar_log()

            # Executar coleta
            sucesso = self.coletar()

            # Finalizar log
            if sucesso:
                self._finalizar_log(
                    'sucesso',
                    f"Coleta concluída com sucesso. Total: {self.docs_novos + self.docs_atualizados} documentos."
                )
            else:
                self._finalizar_log(
                    'erro',
                    'Coleta falhou sem exceção'
                )

            return sucesso

        except Exception as e:
            logger.error(f"Erro na execução do scraper {self.fonte.nome}: {e}", exc_info=True)
            self._finalizar_log(
                'erro',
                f'Erro durante execução: {str(e)}',
                erro=str(e)
            )
            return False

        finally:
            self.session.close()
