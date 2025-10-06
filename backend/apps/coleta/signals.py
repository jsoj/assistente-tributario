"""
Signals para processamento automático de documentos.

Processa arquivos enviados manualmente via admin.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from pathlib import Path
from .models import DocumentoFonte

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DocumentoFonte)
def processar_arquivo_upload(sender, instance, **kwargs):
    """
    Processa arquivo enviado antes de salvar.

    Extrai conteúdo, calcula hash, define caminho.
    """
    if not instance.arquivo_upload:
        return

    # Se já foi processado, não reprocessar
    if instance.pk:
        try:
            old_instance = DocumentoFonte.objects.get(pk=instance.pk)
            if old_instance.arquivo_upload == instance.arquivo_upload:
                return  # Arquivo não mudou
        except DocumentoFonte.DoesNotExist:
            pass

    try:
        logger.info(f"Processando upload: {instance.arquivo_upload.name}")

        # Ler conteúdo do arquivo
        instance.arquivo_upload.seek(0)
        conteudo_bytes = instance.arquivo_upload.read()
        instance.arquivo_upload.seek(0)  # Reset para Django salvar

        # Determinar tipo de conteúdo
        nome_arquivo = instance.arquivo_upload.name.lower()

        if nome_arquivo.endswith('.pdf'):
            # Para PDF, vamos processar no Bloco 2 (Extração)
            # Por agora, apenas salvar binário
            conteudo_texto = f"[PDF Binary: {len(conteudo_bytes)} bytes]"
            logger.info(f"PDF detectado: {len(conteudo_bytes)} bytes")

        elif nome_arquivo.endswith(('.html', '.htm')):
            # HTML - decodificar
            try:
                conteudo_texto = conteudo_bytes.decode('utf-8')
            except UnicodeDecodeError:
                conteudo_texto = conteudo_bytes.decode('latin-1')
            logger.info(f"HTML detectado: {len(conteudo_texto)} caracteres")

        elif nome_arquivo.endswith('.txt'):
            # Texto simples
            try:
                conteudo_texto = conteudo_bytes.decode('utf-8')
            except UnicodeDecodeError:
                conteudo_texto = conteudo_bytes.decode('latin-1')
            logger.info(f"TXT detectado: {len(conteudo_texto)} caracteres")

        else:
            # Outros tipos - tratar como binário
            conteudo_texto = f"[Binary file: {len(conteudo_bytes)} bytes]"
            logger.warning(f"Tipo de arquivo desconhecido: {nome_arquivo}")

        # Calcular hash
        instance.hash_conteudo = DocumentoFonte.calcular_hash(conteudo_texto)

        # Definir tamanho
        instance.tamanho_bytes = len(conteudo_bytes)

        # Definir caminho (será o caminho do FileField)
        instance.caminho_arquivo = str(instance.arquivo_upload.name)

        # Auto-preencher título se vazio
        if not instance.titulo:
            instance.titulo = Path(instance.arquivo_upload.name).stem

        # Auto-preencher identificador se vazio
        if not instance.identificador_externo:
            instance.identificador_externo = f"upload_{instance.hash_conteudo[:12]}"

        # Definir status
        instance.status = 'coletado'

        logger.info(
            f"Upload processado: {instance.titulo} | "
            f"Hash: {instance.hash_conteudo[:12]}... | "
            f"Tamanho: {instance.tamanho_bytes} bytes"
        )

    except Exception as e:
        logger.error(f"Erro ao processar upload: {e}", exc_info=True)
        raise


@receiver(post_save, sender=DocumentoFonte)
def log_documento_salvo(sender, instance, created, **kwargs):
    """Log quando documento é criado ou atualizado."""
    if created:
        logger.info(f"Novo documento criado: {instance.titulo} (ID: {instance.pk})")
        if instance.arquivo_upload:
            logger.info(f"  → Via upload: {instance.arquivo_upload.name}")
    else:
        logger.info(f"Documento atualizado: {instance.titulo} (ID: {instance.pk})")
