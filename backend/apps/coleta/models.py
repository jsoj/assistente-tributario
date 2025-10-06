"""
Models para o app de Coleta (Bloco 1).

Responsável por armazenar metadados sobre documentos coletados
e logs de execução dos scrapers.
"""
from django.db import models
from django.utils import timezone
import hashlib


class FonteDados(models.Model):
    """
    Fonte de dados configurada para coleta.

    Representa um site/API/recurso de onde coletamos documentos.
    """
    TIPO_CHOICES = [
        ('web', 'Website'),
        ('api', 'API'),
        ('pdf', 'PDF Direto'),
        ('rss', 'RSS Feed'),
    ]

    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('erro', 'Com Erro'),
    ]

    nome = models.CharField(max_length=200, unique=True)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    url_base = models.URLField(max_length=500)

    # Configurações
    frequencia_coleta = models.CharField(
        max_length=50,
        default='diaria',
        help_text='Ex: diaria, semanal, mensal'
    )
    scraper_class = models.CharField(
        max_length=200,
        help_text='Nome da classe Python do scraper (ex: CositScraper)'
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')
    ativo = models.BooleanField(default=True)

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ultima_coleta = models.DateTimeField(null=True, blank=True)
    proxima_coleta = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Fonte de Dados'
        verbose_name_plural = 'Fontes de Dados'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.tipo})"


class DocumentoFonte(models.Model):
    """
    Documento coletado de uma fonte.

    Armazena metadados sobre o documento bruto coletado.
    O conteúdo real fica em /data/raw/
    """
    TIPO_CHOICES = [
        ('lei', 'Lei'),
        ('resolucao', 'Resolução'),
        ('consulta', 'Solução de Consulta'),
        ('pergunta', 'Pergunta e Resposta'),
        ('ato', 'Ato Declaratório'),
        ('outro', 'Outro'),
    ]

    STATUS_CHOICES = [
        ('coletado', 'Coletado'),
        ('processando', 'Processando'),
        ('processado', 'Processado'),
        ('erro', 'Erro'),
    ]

    fonte = models.ForeignKey(FonteDados, on_delete=models.CASCADE, related_name='documentos')

    # Identificação
    titulo = models.CharField(max_length=500)
    tipo_documento = models.CharField(max_length=50, choices=TIPO_CHOICES)
    url_origem = models.URLField(max_length=1000)
    identificador_externo = models.CharField(
        max_length=200,
        blank=True,
        help_text='ID do documento no site de origem'
    )

    # Conteúdo
    hash_conteudo = models.CharField(
        max_length=64,
        help_text='SHA256 do conteúdo bruto para detectar mudanças'
    )
    caminho_arquivo = models.CharField(
        max_length=500,
        help_text='Caminho relativo em /data/raw/'
    )
    tamanho_bytes = models.IntegerField(default=0)

    # Metadados do documento
    data_publicacao = models.DateField(null=True, blank=True)
    orgao_emissor = models.CharField(max_length=200, blank=True)
    numero_documento = models.CharField(max_length=100, blank=True)

    # Status de processamento
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='coletado')
    versao = models.IntegerField(default=1)

    # Timestamps
    coletado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Documento Fonte'
        verbose_name_plural = 'Documentos Fonte'
        ordering = ['-coletado_em']
        indexes = [
            models.Index(fields=['fonte', 'status']),
            models.Index(fields=['hash_conteudo']),
            models.Index(fields=['-coletado_em']),
        ]
        unique_together = [['fonte', 'identificador_externo']]

    def __str__(self):
        return f"{self.titulo} - {self.fonte.nome}"

    @staticmethod
    def calcular_hash(conteudo: str) -> str:
        """Calcula SHA256 de um conteúdo."""
        return hashlib.sha256(conteudo.encode('utf-8')).hexdigest()


class LogColeta(models.Model):
    """
    Log de execução de scrapers.

    Registra cada execução de coleta para auditoria e debugging.
    """
    STATUS_CHOICES = [
        ('iniciado', 'Iniciado'),
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado'),
    ]

    fonte = models.ForeignKey(FonteDados, on_delete=models.CASCADE, related_name='logs')

    # Execução
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='iniciado')
    iniciado_em = models.DateTimeField(default=timezone.now)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    duracao_segundos = models.IntegerField(null=True, blank=True)

    # Resultados
    documentos_novos = models.IntegerField(default=0)
    documentos_atualizados = models.IntegerField(default=0)
    documentos_ignorados = models.IntegerField(default=0)
    documentos_erro = models.IntegerField(default=0)

    # Detalhes
    mensagem = models.TextField(blank=True)
    erro_detalhe = models.TextField(blank=True)
    metadados = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dados adicionais em JSON'
    )

    class Meta:
        verbose_name = 'Log de Coleta'
        verbose_name_plural = 'Logs de Coleta'
        ordering = ['-iniciado_em']
        indexes = [
            models.Index(fields=['fonte', '-iniciado_em']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.fonte.nome} - {self.status} ({self.iniciado_em})"

    def calcular_duracao(self):
        """Calcula duração da execução."""
        if self.finalizado_em and self.iniciado_em:
            delta = self.finalizado_em - self.iniciado_em
            self.duracao_segundos = int(delta.total_seconds())
