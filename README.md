# API de Normativas EGESUR

API REST para consultar normativas y documentos técnicos de EGESUR mediante búsqueda semántica con IA.

## 🚀 Características

- **Búsqueda semántica** con embeddings de OpenAI
- **Integración con Google Drive** para almacenamiento de documentos
- **Persistencia en PostgreSQL** para optimizar tiempos de respuesta
- **Integración con ChatGPT Custom Actions**
- **Soporte para múltiples formatos**: PDF, DOCX, Google Docs

## 📁 Estructura del Repositorio

```
EGESUR-AsistenteNormativo/
├── src/                    # Código fuente
│   ├── main.py            # API principal (FastAPI)
│   └── test_openai.py     # Test de conectividad OpenAI
├── docs/                   # Documentación
│   ├── README.md          # Documentación técnica detallada
│   ├── CLAUDE.md          # Guía para desarrolladores
│   └── POSTGRESQL_SETUP.md # Configuración de base de datos
├── gpt/                    # Configuración ChatGPT
│   ├── PROMPT_OPTIMIZADO.md  # Prompt del GPT personalizado
│   └── SCHEMA_OPENAPI.md     # Schema para Custom Actions
├── latex/                  # Documento de transferencia técnica
│   ├── transferencia_tecnica.tex  # Documento LaTeX
│   └── README.md          # Instrucciones de compilación
├── .env.example           # Template de variables de entorno
├── .gitignore            # Exclusiones de git
├── requirements.txt      # Dependencias Python
└── runtime.txt           # Versión de Python
```

## 🛠️ Tecnologías

- **Framework**: FastAPI
- **Base de Datos**: PostgreSQL
- **Almacenamiento**: Google Drive API
- **IA**: OpenAI text-embedding-3-small
- **Python**: 3.12.3
- **Despliegue**: Railway/Render

## ⚡ Inicio Rápido

### 1. Instalación

```bash
# Clonar repositorio
git clone https://github.com/anjos3/EGESUR-AsistenteNormativo.git
cd EGESUR-AsistenteNormativo

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Configuración

Editar `.env` con las siguientes variables:

```bash
FOLDER_ID=<ID_de_carpeta_Google_Drive>
GOOGLE_CREDENTIALS_BASE64=<credenciales_base64>
OPENAI_API_KEY=<tu_api_key_openai>
DATABASE_URL=postgresql://user:pass@host:5432/db
```

### 3. Ejecución

```bash
# Desarrollo
uvicorn src.main:app --reload

# Producción
python src/main.py
```

### 4. Primera Vez

```bash
# Precargar documentos (10-15 minutos)
curl http://localhost:8000/api/warmup

# Verificar estado
curl http://localhost:8000/api/debug/cache-status
```

## 📚 Documentación Completa

- **[docs/README.md](docs/README.md)** - Documentación técnica completa
- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Guía para desarrolladores
- **[docs/POSTGRESQL_SETUP.md](docs/POSTGRESQL_SETUP.md)** - Setup de PostgreSQL
- **[latex/transferencia_tecnica.tex](latex/transferencia_tecnica.tex)** - Documento de transferencia técnica

## 🔌 Endpoints Principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/buscarNormativa` | GET | Búsqueda semántica de documentos |
| `/api/warmup` | GET | Precargar documentos |
| `/api/refresh-cache` | POST | Actualizar caché |
| `/ping` | GET | Health check |
| `/api/debug/*` | GET | Endpoints de diagnóstico |

## 🚢 Despliegue en Producción

### Railway/Render

1. **Crear servicio web**
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

2. **Crear PostgreSQL**
   - Plan gratuito: 256 MB (suficiente para ~70 PDFs)

3. **Configurar variables de entorno**
   - Ver `.env.example` para referencia

4. **Primera ejecución**
   ```bash
   curl -X GET "https://tu-servicio.onrender.com/api/warmup"
   ```

Ver [docs/POSTGRESQL_SETUP.md](docs/POSTGRESQL_SETUP.md) para guía detallada.

## 🔧 Mantenimiento

### Actualizar Documentos

```bash
# 1. Subir/modificar archivos en Google Drive
# 2. Refrescar caché
curl -X POST "https://tu-servicio.onrender.com/api/refresh-cache"
```

### Monitoreo

```bash
# Estado del caché
curl https://tu-servicio.onrender.com/api/debug/cache-status

# Verificar OpenAI
curl https://tu-servicio.onrender.com/api/debug/test-openai

# Verificar Google Drive
curl https://tu-servicio.onrender.com/api/debug/test-drive
```

## 🤖 Integración con ChatGPT

El sistema está diseñado para integrarse con ChatGPT Custom Actions. Ver:
- **[gpt/PROMPT_OPTIMIZADO.md](gpt/PROMPT_OPTIMIZADO.md)** - Prompt del GPT
- **[gpt/SCHEMA_OPENAPI.md](gpt/SCHEMA_OPENAPI.md)** - Schema OpenAPI

## 📄 Documento de Transferencia Técnica

Para el equipo de TI de EGESUR, hemos preparado un documento completo de transferencia técnica en LaTeX:

```bash
cd latex
pdflatex transferencia_tecnica.tex
# Genera: transferencia_tecnica.pdf
```

Ver [latex/README.md](latex/README.md) para opciones de compilación.

## 🔒 Seguridad

- ✅ Google Service Account con permisos de solo lectura
- ✅ Variables de entorno para credenciales
- ✅ `.gitignore` configurado para excluir secretos
- ⚠️ CORS habilitado para todos los orígenes (restringir en producción)
- ⚠️ Sin rate limiting (agregar en producción)

## 📞 Soporte

Para preguntas técnicas, consultar:
1. [docs/README.md](docs/README.md) - Documentación técnica
2. [latex/transferencia_tecnica.pdf](latex/transferencia_tecnica.pdf) - Documento de transferencia
3. Issues en GitHub

## 📝 Licencia

Propiedad de EGESUR - Empresa de Generación Eléctrica del Sur S.A.

---

**Versión:** 1.0
**Última actualización:** Noviembre 2025
**Estado:** Producción
