# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Descripción del Proyecto

EGESUR Asistente Normativo - API REST con FastAPI que proporciona búsqueda semántica sobre documentos normativos almacenados en Google Drive. El sistema descarga archivos PDF y DOCX desde Google Drive, genera embeddings usando la API de OpenAI, y proporciona capacidades de búsqueda semántica rápida para integración con ChatGPT Custom Actions.

## Comandos Comunes

### Desarrollo
```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar localmente (modo desarrollo con auto-reload)
uvicorn main:app --reload

# Ejecutar localmente (modo producción)
python main.py

# Probar conexión con OpenAI API
python test_openai.py

# Ver documentación de la API
# Navegar a http://localhost:8000/docs
```

### Probar Endpoints
```bash
# Health check
curl http://localhost:8000/

# Precalentar caché (pre-cargar todos los documentos y generar embeddings)
curl http://localhost:8000/api/warmup

# Refrescar caché (forzar recarga desde Google Drive)
curl -X POST http://localhost:8000/api/refresh-cache

# Buscar normativas (búsqueda semántica)
curl "http://localhost:8000/api/buscarNormativa?termino=emergencia"

# Endpoints de debug
curl http://localhost:8000/api/debug/env
curl http://localhost:8000/api/debug/test-drive
curl http://localhost:8000/api/debug/cache-status
curl http://localhost:8000/api/debug/test-openai
```

## Arquitectura

### Componentes Principales

**main.py** (1238 líneas) - Aplicación FastAPI en un solo archivo con la siguiente arquitectura:

1. **Integración con Google Drive** (líneas 110-147)
   - Autenticación con Service Account con soporte para credenciales codificadas en base64
   - Descarga archivos PDF, DOCX y Google Docs
   - Extracción de texto usando PyPDF2 y python-docx

2. **Generación de Embeddings y Búsqueda Semántica** (líneas 450-591)
   - Divide documentos en chunks de ~3000 caracteres con 300 caracteres de solapamiento
   - Genera embeddings usando el modelo `text-embedding-3-small` de OpenAI
   - Búsqueda por similitud de coseno para recuperar documentos relevantes

3. **Sistema de Caché de Dos Niveles** (líneas 99-216, 231-327)
   - **Caché en Memoria (dict CACHE)**: Acceso rápido durante ejecución (TTL: ~100 años, efectivamente infinito)
   - **Persistencia en PostgreSQL (tabla document_chunks)**: Sobrevive reinicios del servicio en plataformas como Render/Railway
   - Caché solo se actualiza mediante llamadas explícitas a `/api/refresh-cache` o `/api/warmup`
   - Al iniciar carga desde PostgreSQL si está disponible (2-5 segundos vs 10+ minutos de regeneración)

4. **Esquema de Base de Datos** (líneas 65-81)
   ```
   Tabla document_chunks:
   - chunk_id (PK): "file_id_index"
   - text: Contenido del chunk (~3000 chars)
   - embedding: Array JSONB de 1536 floats
   - source_document: Nombre del archivo PDF
   - source_link: URL de Google Drive
   - chunk_index/total_chunks: Metadata de posición
   - folder_id: ID de carpeta de Drive
   - created_at: Timestamp
   ```

5. **Endpoints de la API**
   - `GET /api/buscarNormativa` (líneas 1047-1232): Endpoint principal de búsqueda con búsqueda semántica
   - `GET /api/warmup` (líneas 837-1010): Pre-poblar caché después del despliegue
   - `POST /api/refresh-cache` (líneas 1013-1044): Forzar reconstrucción del caché cuando cambia contenido en Drive
   - `GET /ping` (línea 708): Health check para monitoreo de uptime
   - Endpoints de debug (líneas 714-834): Diagnósticos de entorno, Drive, caché y OpenAI

### Flujo de Datos

1. **Despliegue Inicial / Caché Vacío**:
   ```
   Usuario → /api/warmup → Google Drive → Descargar todos los PDFs → Extraer texto →
   Dividir en chunks → Generar embeddings (OpenAI) → Guardar en PostgreSQL + CACHE
   ```

2. **Reinicio del Servicio** (ej: Render despierta del modo sleep):
   ```
   startup_event (línea 653) → load_chunks_from_db() → Poblar CACHE → Listo (2-5 seg)
   ```

3. **Solicitud de Búsqueda** (ruta rápida):
   ```
   /api/buscarNormativa?termino=X → semantic_search() → Similitud de coseno en CACHE →
   Retornar top 10 chunks (< 10 segundos)
   ```

4. **Flujo de Actualización de Contenido**:
   ```
   Admin sube nuevo PDF a Drive → Llamar /api/refresh-cache → Invalidar caché →
   Re-descargar todos los archivos → Regenerar embeddings → Actualizar PostgreSQL + CACHE
   ```

## Variables de Entorno

Variables requeridas (configurar en `.env` localmente o en plataforma de despliegue):

- `FOLDER_ID`: ID de carpeta de Google Drive que contiene documentos normativos
- `GOOGLE_CREDENTIALS_BASE64`: JSON de service account de Google codificado en base64 (producción)
- `GOOGLE_APPLICATION_CREDENTIALS`: Ruta al archivo de credenciales (fallback desarrollo, default: `credenciales.json`)
- `OPENAI_API_KEY`: API key de OpenAI para generación de embeddings
- `DATABASE_URL`: String de conexión a PostgreSQL (formato: `postgresql://user:pass@host/db`)

## Patrones de Diseño Clave

### Optimización de Inicio
El sistema prioriza experiencia de usuario sin timeouts mediante:
- Carga de embeddings pre-generados desde PostgreSQL al iniciar (líneas 653-686)
- Uso de caché con TTL infinito que solo se refresca por solicitud explícita del admin
- Separación de operaciones de admin (`/api/refresh-cache`) de operaciones de usuario (`/api/buscarNormativa`)

### Credenciales de Modo Dual
Soporta tanto desarrollo local como despliegue en la nube (líneas 120-139):
- Verifica `GOOGLE_CREDENTIALS_BASE64` primero (Railway/Render)
- Hace fallback al archivo `credenciales.json` (desarrollo local)

### Degradación Elegante
- La API funciona sin PostgreSQL (advierte pero continúa con caché solo en memoria)
- La API funciona sin API key de OpenAI (deshabilita búsqueda semántica, advierte en logs)

## Notas de Despliegue en Producción

### Despliegue en Railway/Render
- El servicio está diseñado para plataformas con sistemas de archivos efímeros que duermen tras inactividad
- Persistencia en PostgreSQL asegura que los embeddings sobrevivan reinicios (ver POSTGRESQL_SETUP.md)
- PostgreSQL tier gratuito (256 MB) soporta ~600 chunks (~17 PDFs con capacidad de ~4,200 chunks)

### Monitoreo
Buscar estos patrones en los logs:
- `✓` = Operaciones exitosas
- `⚠️` = Advertencias (funcionalidad degradada)
- `✗` = Errores
- `🔥` = Operaciones de precalentamiento de caché
- `⚡` = Aciertos de caché rápidos

### Gestión de Caché
- **Primer despliegue**: Llamar `/api/warmup` para poblar caché (~10-15 minutos para 17 PDFs)
- **Después de actualizar contenido en Drive**: Llamar `/api/refresh-cache`
- **Después de reinicio del servicio**: Caché se carga automáticamente desde PostgreSQL si está disponible
- **El caché nunca expira** a menos que se refresque o limpie manualmente

## Integración con ChatGPT Custom Actions

Esta API está diseñada como backend para GPTs personalizados de ChatGPT. Ver SCHEMA_GPT_ACTUALIZADO.md para el esquema OpenAPI. El endpoint `/api/buscarNormativa` retorna texto formateado optimizado para consumo de GPT con metadata de documentos y scores de relevancia.

## Consideraciones de Seguridad

- La service account de Google tiene acceso de solo lectura a Drive (SCOPES en línea 49)
- CORS habilitado para todos los orígenes (línea 36) - restringir en producción
- Credenciales excluidas de git mediante .gitignore
- No hay rate limiting implementado - agregar para uso en producción
