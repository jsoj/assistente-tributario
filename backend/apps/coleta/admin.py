"""
Admin interface para o app de Coleta.

Permite gerenciar fontes de dados, documentos coletados e logs
através da interface administrativa do Django.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import FonteDados, DocumentoFonte, LogColeta


@admin.register(FonteDados)
class FonteDadosAdmin(admin.ModelAdmin):
    """Admin para gerenciar fontes de dados."""

    list_display = [
        'nome',
        'tipo',
        'status',
        'ativo',
        'total_documentos',
        'ultima_coleta',
        'proxima_coleta'
    ]

    list_filter = ['tipo', 'status', 'ativo', 'frequencia_coleta']

    search_fields = ['nome', 'descricao', 'url_base']

    readonly_fields = ['criado_em', 'atualizado_em', 'ultima_coleta']

    fieldsets = [
        ('Identificação', {
            'fields': ['nome', 'descricao', 'tipo']
        }),
        ('Configuração', {
            'fields': ['url_base', 'scraper_class', 'frequencia_coleta']
        }),
        ('Status', {
            'fields': ['status', 'ativo']
        }),
        ('Timestamps', {
            'fields': ['criado_em', 'atualizado_em', 'ultima_coleta', 'proxima_coleta'],
            'classes': ['collapse']
        }),
    ]

    def total_documentos(self, obj):
        """Mostra total de documentos coletados."""
        total = obj.documentos.count()
        url = reverse('admin:coleta_documentofonte_changelist') + f'?fonte__id__exact={obj.id}'
        return format_html('<a href="{}">{} docs</a>', url, total)

    total_documentos.short_description = 'Documentos'


@admin.register(DocumentoFonte)
class DocumentoFonteAdmin(admin.ModelAdmin):
    """Admin para documentos coletados."""

    list_display = [
        'titulo_truncado',
        'fonte',
        'tipo_documento',
        'status',
        'versao',
        'tamanho_kb',
        'coletado_em'
    ]

    list_filter = [
        'fonte',
        'tipo_documento',
        'status',
        'data_publicacao',
        'coletado_em'
    ]

    search_fields = [
        'titulo',
        'identificador_externo',
        'numero_documento',
        'orgao_emissor'
    ]

    readonly_fields = [
        'hash_conteudo',
        'caminho_arquivo',
        'tamanho_bytes',
        'coletado_em',
        'atualizado_em',
        'link_url'
    ]

    fieldsets = [
        ('Identificação', {
            'fields': ['fonte', 'titulo', 'tipo_documento', 'identificador_externo']
        }),
        ('Metadados do Documento', {
            'fields': ['numero_documento', 'orgao_emissor', 'data_publicacao']
        }),
        ('Conteúdo', {
            'fields': ['hash_conteudo', 'caminho_arquivo', 'tamanho_bytes', 'link_url']
        }),
        ('Status', {
            'fields': ['status', 'versao']
        }),
        ('Timestamps', {
            'fields': ['coletado_em', 'atualizado_em'],
            'classes': ['collapse']
        }),
    ]

    date_hierarchy = 'coletado_em'

    def titulo_truncado(self, obj):
        """Mostra título truncado."""
        if len(obj.titulo) > 80:
            return obj.titulo[:80] + '...'
        return obj.titulo

    titulo_truncado.short_description = 'Título'

    def tamanho_kb(self, obj):
        """Mostra tamanho em KB."""
        return f"{obj.tamanho_bytes / 1024:.1f} KB"

    tamanho_kb.short_description = 'Tamanho'

    def link_url(self, obj):
        """Link clicável para URL de origem."""
        if obj.url_origem:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.url_origem, obj.url_origem)
        return '-'

    link_url.short_description = 'URL de Origem'


@admin.register(LogColeta)
class LogColetaAdmin(admin.ModelAdmin):
    """Admin para logs de execução."""

    list_display = [
        'id',
        'fonte',
        'status_badge',
        'iniciado_em',
        'duracao',
        'total_processados',
        'documentos_novos',
        'documentos_erro'
    ]

    list_filter = ['status', 'fonte', 'iniciado_em']

    search_fields = ['fonte__nome', 'mensagem', 'erro_detalhe']

    readonly_fields = [
        'fonte',
        'status',
        'iniciado_em',
        'finalizado_em',
        'duracao_segundos',
        'documentos_novos',
        'documentos_atualizados',
        'documentos_ignorados',
        'documentos_erro',
        'mensagem',
        'erro_detalhe',
        'metadados'
    ]

    fieldsets = [
        ('Execução', {
            'fields': ['fonte', 'status', 'iniciado_em', 'finalizado_em', 'duracao_segundos']
        }),
        ('Resultados', {
            'fields': [
                'documentos_novos',
                'documentos_atualizados',
                'documentos_ignorados',
                'documentos_erro'
            ]
        }),
        ('Detalhes', {
            'fields': ['mensagem', 'erro_detalhe', 'metadados'],
            'classes': ['collapse']
        }),
    ]

    date_hierarchy = 'iniciado_em'

    def has_add_permission(self, request):
        """Logs não devem ser criados manualmente."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Logs não devem ser deletados."""
        return False

    def status_badge(self, obj):
        """Badge colorido para status."""
        cores = {
            'sucesso': '#28a745',
            'erro': '#dc3545',
            'iniciado': '#ffc107',
            'cancelado': '#6c757d'
        }
        cor = cores.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            cor,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'

    def duracao(self, obj):
        """Formata duração."""
        if obj.duracao_segundos is not None:
            if obj.duracao_segundos < 60:
                return f"{obj.duracao_segundos}s"
            minutos = obj.duracao_segundos // 60
            segundos = obj.duracao_segundos % 60
            return f"{minutos}m {segundos}s"
        return '-'

    duracao.short_description = 'Duração'

    def total_processados(self, obj):
        """Total de documentos processados."""
        return obj.documentos_novos + obj.documentos_atualizados

    total_processados.short_description = 'Total Proc.'
