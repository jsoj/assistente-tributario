# Assistente Tributário de IA

**Status:** Em Desenvolvimento
**Versão:** 0.1.0
**Data:** 2025-10-06

## 📋 Visão Geral

Assistente de IA especializado em legislação tributária brasileira, focado em **Comércio no Simples Nacional**. Utiliza RAG (Retrieval-Augmented Generation) para fornecer respostas precisas e auditáveis com citação de fontes.

## 🏗️ Arquitetura

### 4 Blocos de Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   BLOCO 1   │────▶│   BLOCO 2   │────▶│   BLOCO 3   │────▶│   BLOCO 4   │
│   COLETA    │     │  EXTRAÇÃO   │     │ENRIQUECIMENTO│    │ARMAZENAMENTO│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

1. **Coleta** (`apps/coleta`): Web scrapers para fontes governamentais
2. **Extração** (`apps/extracao`): Parsing e limpeza de documentos
3. **Enriquecimento** (`apps/enriquecimento`): Embeddings e metadados
4. **Armazenamento** (`apps/armazenamento`): Vector DB e versionamento

### Apps Adicionais

- **RAG** (`apps/rag`): Motor de recuperação e geração
- **Chat** (`apps/chat`): Interface de conversação
- **API** (`apps/api`): REST API endpoints

## 🚀 Quick Start

### 1. Setup

```bash
# Clone o repositório
git clone <repo-url>
cd assistente-tributario

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r backend/requirements.txt

# Configurar .env
cp .env.example .env
# Edite .env com suas configurações
```

### 2. Database

```bash
# PostgreSQL já configurado em: assistente_tributario
# User: tributario_user
# Password: veja .env

# Rodar migrações
cd backend
python manage.py migrate

# Criar superuser
python manage.py createsuperuser
```

### 3. Ollama (IA)

```bash
# Verificar modelos disponíveis
ollama list

# Adicionar Mistral 7B (se não existir)
ollama pull mistral:7b-instruct

# Testar
curl http://localhost:11434/api/tags
```

### 4. Run

```bash
# Dev server
python manage.py runserver 0.0.0.0:8010

# Celery worker (terminal separado)
celery -A config worker -l info

# Celery beat (agendamento)
celery -A config beat -l info
```

Acesse: http://localhost:8010

## 📁 Estrutura

```
/projects/assistente-tributario/
├── backend/                    # Django project
│   ├── config/                # Settings
│   ├── apps/
│   │   ├── coleta/           # Bloco 1
│   │   ├── extracao/         # Bloco 2
│   │   ├── enriquecimento/   # Bloco 3
│   │   ├── armazenamento/    # Bloco 4
│   │   ├── rag/              # RAG engine
│   │   ├── chat/             # Chat UI
│   │   └── api/              # REST API
│   ├── manage.py
│   └── requirements.txt
├── data/                      # Dados (gitignored)
│   ├── raw/                  # Scraped data
│   ├── cleaned/              # Parsed data
│   ├── enriched/             # Embeddings
│   └── vectordb/             # ChromaDB
├── docs/                     # Documentação
├── frontend/                 # Templates + Static
├── venv/                     # Virtual env (gitignored)
├── .env                      # Config (gitignored)
└── README.md
```

## 🔧 Tech Stack

- **Backend:** Django 5.0 + DRF + Celery
- **Database:** PostgreSQL 15+
- **Cache/Queue:** Redis
- **LLM:** Mistral 7B (via Ollama)
- **Embeddings:** nomic-embed-text (Ollama)
- **Reranker:** BAAI/bge-reranker-v2-m3 @ localhost:8002
- **Vector DB:** ChromaDB (dev) → Qdrant (prod)
- **Frontend:** Django Templates + HTMX + TailwindCSS

## 📚 Documentação

- **Spec completa:** `/espec_IA_tributaria.md`
- **Quick ref:** `/QUICKREF_IA_tributaria.md`
- **VPS info:** `/CLAUDE.md`
- **Docs:** `/projects/assistente-tributario/docs/`

## 🎯 Roadmap

### Sprint 1 (Semana 1-2) - Foundation
- [x] Setup projeto Django
- [x] Configurar PostgreSQL
- [x] Estrutura de apps
- [ ] Implementar ScraperBase
- [ ] Primeiro scraper (COSIT)

### Sprint 2 (Semana 3-4) - Pipeline Bloco 1 & 2
- [ ] Completar 5 scrapers
- [ ] Celery tasks agendamento
- [ ] Parsers HTML/PDF
- [ ] Testes unitários

## 🧪 Testes

```bash
# Rodar testes
pytest

# Com coverage
pytest --cov=apps
```

## 📝 Licença

Proprietary - Uso interno

## 👥 Contato

Owner: junior31maio@gmail.com

---

**Desenvolvido com Django + Ollama + RAG**
