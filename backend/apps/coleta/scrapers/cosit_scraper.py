"""
Scraper para Soluções de Consulta COSIT - Receita Federal.

Coleta soluções de consulta publicadas pela Coordenação-Geral de Tributação (COSIT).
URL: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/solucoes-de-consulta
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

from ..scraper_base import ScraperBase

logger = logging.getLogger(__name__)


class CositScraper(ScraperBase):
    """
    Scraper específico para Soluções de Consulta COSIT.

    Coleta documentos da página de soluções de consulta da Receita Federal,
    organizados por ano.
    """

    # URLs base
    BASE_URL = "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/legislacao/solucoes-de-consulta"

    def validar_configuracao(self) -> bool:
        """
        Valida se a fonte está configurada corretamente para COSIT.

        Returns:
            True se válida, False caso contrário
        """
        if not self.fonte.url_base:
            logger.error("URL base não configurada")
            return False

        if self.fonte.tipo != 'web':
            logger.error(f"Tipo incorreto: {self.fonte.tipo}. Esperado: 'web'")
            return False

        return True

    def _extrair_ano_atual(self) -> int:
        """Retorna o ano atual para buscar documentos recentes."""
        return datetime.now().year

    def _obter_lista_anos(self) -> List[int]:
        """
        Obtém lista de anos disponíveis na página.

        Por padrão, coleta últimos 2 anos para o MVP.
        Pode ser configurado para coletar mais anos depois.
        """
        ano_atual = self._extrair_ano_atual()
        # MVP: Coletar apenas últimos 2 anos
        return [ano_atual, ano_atual - 1]

    def _construir_url_ano(self, ano: int) -> str:
        """
        Constrói URL para página de um ano específico.

        Args:
            ano: Ano (ex: 2024)

        Returns:
            URL completa
        """
        return f"{self.BASE_URL}/{ano}"

    def _parsear_pagina_ano(self, html: str, ano: int) -> List[Dict]:
        """
        Faz parsing da página HTML de um ano e extrai documentos.

        Args:
            html: Conteúdo HTML da página
            ano: Ano sendo processado

        Returns:
            Lista de dicionários com informações dos documentos
        """
        soup = BeautifulSoup(html, 'html.parser')
        documentos = []

        # Procurar por links de documentos
        # A estrutura pode variar, mas geralmente são tabelas ou listas
        # Vamos procurar por padrões comuns

        # Padrão 1: Links diretos em listas
        links = soup.find_all('a', href=True)

        for link in links:
            href = link.get('href', '')
            texto = link.get_text(strip=True)

            # Filtrar links que parecem ser soluções de consulta
            # Exemplo: "Solução de Consulta nº 1234/2024"
            if self._e_solucao_consulta(texto, href):
                doc_info = self._extrair_info_documento(link, href, texto, ano)
                if doc_info:
                    documentos.append(doc_info)

        logger.info(f"Encontrados {len(documentos)} documentos para o ano {ano}")
        return documentos

    def _e_solucao_consulta(self, texto: str, href: str) -> bool:
        """
        Verifica se um link é uma solução de consulta válida.

        Args:
            texto: Texto do link
            href: URL do link

        Returns:
            True se for solução de consulta
        """
        # Padrões comuns:
        # - "Solução de Consulta nº"
        # - "Solução de Consulta Cosit nº"
        # - Arquivo PDF
        texto_lower = texto.lower()
        href_lower = href.lower()

        if 'solução de consulta' in texto_lower or 'solucao de consulta' in texto_lower:
            return True

        if 'cosit' in texto_lower and ('nº' in texto_lower or 'n°' in texto_lower or 'no' in texto_lower):
            return True

        if href_lower.endswith('.pdf') and 'consul' in href_lower:
            return True

        return False

    def _extrair_info_documento(self, link_element, href: str, texto: str, ano: int) -> Optional[Dict]:
        """
        Extrai informações detalhadas de um documento.

        Args:
            link_element: Elemento BeautifulSoup do link
            href: URL do documento
            texto: Texto do link
            ano: Ano do documento

        Returns:
            Dicionário com informações ou None se inválido
        """
        try:
            # Extrair número da solução
            # Padrões: "nº 123", "n° 123", "no 123/2024"
            numero_match = re.search(r'n[°º]?\s*(\d+)(?:/(\d{4}))?', texto, re.IGNORECASE)

            if not numero_match:
                return None

            numero = numero_match.group(1)
            ano_doc = numero_match.group(2) if numero_match.group(2) else str(ano)

            # Construir URL completa se relativa
            if href.startswith('http'):
                url_completa = href
            else:
                url_completa = f"https://www.gov.br{href}" if href.startswith('/') else f"{self.BASE_URL}/{href}"

            # Identificador único
            identificador = f"cosit_{ano_doc}_{numero.zfill(4)}"

            # Criar dicionário com informações
            doc_info = {
                'identificador': identificador,
                'titulo': texto[:500],  # Limitar tamanho
                'url': url_completa,
                'numero': numero,
                'ano': int(ano_doc),
                'tipo': 'consulta',
            }

            return doc_info

        except Exception as e:
            logger.warning(f"Erro ao extrair info do documento: {e}")
            return None

    def _baixar_documento(self, url: str) -> Optional[str]:
        """
        Baixa o conteúdo de um documento.

        Args:
            url: URL do documento

        Returns:
            Conteúdo HTML/texto ou None se falhar
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text

        except Exception as e:
            logger.error(f"Erro ao baixar {url}: {e}")
            return None

    def coletar(self) -> bool:
        """
        Implementação principal da coleta COSIT.

        Returns:
            True se sucesso, False se erro
        """
        try:
            logger.info(f"Iniciando coleta COSIT de {self.fonte.url_base}")

            anos = self._obter_lista_anos()
            logger.info(f"Coletando anos: {anos}")

            total_processados = 0

            for ano in anos:
                logger.info(f"Processando ano {ano}...")

                # Obter página do ano
                url_ano = self._construir_url_ano(ano)
                html_ano = self._baixar_documento(url_ano)

                if not html_ano:
                    logger.warning(f"Não foi possível baixar página do ano {ano}")
                    continue

                # Parsear página e extrair documentos
                documentos = self._parsear_pagina_ano(html_ano, ano)

                # Processar cada documento
                for doc_info in documentos:
                    try:
                        # Baixar conteúdo do documento
                        conteudo = self._baixar_documento(doc_info['url'])

                        if not conteudo:
                            logger.warning(f"Não foi possível baixar documento {doc_info['identificador']}")
                            self.docs_erro += 1
                            continue

                        # Salvar documento
                        metadados = {
                            'numero_documento': f"{doc_info['numero']}/{doc_info['ano']}",
                            'orgao_emissor': 'COSIT - Receita Federal',
                        }

                        self._salvar_documento(
                            titulo=doc_info['titulo'],
                            conteudo=conteudo,
                            url=doc_info['url'],
                            identificador=doc_info['identificador'],
                            tipo_documento='consulta',
                            metadados=metadados
                        )

                        total_processados += 1

                        # Rate limiting
                        self._delay()

                    except Exception as e:
                        logger.error(f"Erro ao processar documento {doc_info['identificador']}: {e}")
                        self.docs_erro += 1
                        continue

                logger.info(f"Ano {ano} concluído")

            logger.info(f"Coleta COSIT finalizada. Total processados: {total_processados}")
            return total_processados > 0

        except Exception as e:
            logger.error(f"Erro fatal na coleta COSIT: {e}", exc_info=True)
            return False
