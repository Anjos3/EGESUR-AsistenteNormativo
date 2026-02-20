from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2
from docx import Document
import io
import os
import json
import base64
from dotenv import load_dotenv
from typing import Optional, Dict, List
import logging
import unicodedata
from datetime import datetime, timedelta
from openai import OpenAI
import numpy as np
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

app = FastAPI(title="EGESUR - API de Normativas", version="1.0.0")

# Configurar CORS para permitir llamadas desde GPT y otros orígenes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Protege todos los endpoints /api/* con API key via Bearer token."""
    if request.url.path.startswith("/api/") and API_KEY:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "API key requerida. Usa el header: Authorization: Bearer <tu-api-key>"}
            )
        token = auth_header.replace("Bearer ", "")
        if token != API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "API key inválida"}
            )
    response = await call_next(request)
    return response


# Variables de entorno
FOLDER_ID = os.getenv("FOLDER_ID")
GOOGLE_CREDENTIALS_BASE64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Scopes necesarios para Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Configurar cliente de OpenAI
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✓ OpenAI API configurado correctamente para embeddings")
else:
    openai_client = None
    logger.warning("⚠️ OPENAI_API_KEY no configurado - búsqueda semántica deshabilitada")
    logger.warning("⚠️ Sin API key, no se generarán embeddings")

# ====================
# BASE DE DATOS (PostgreSQL)
# ====================
Base = declarative_base()

class DocumentChunk(Base):
    """
    Modelo para almacenar chunks de documentos con sus embeddings en PostgreSQL.
    Permite persistir embeddings entre reinicios del servidor.
    """
    __tablename__ = "document_chunks"

    chunk_id = Column(String, primary_key=True)  # "file_id_index"
    text = Column(Text, nullable=False)  # Contenido del chunk (~3000 chars)
    embedding = Column(JSONB, nullable=False)  # Array de 1536 floats como JSON
    source_document = Column(String, nullable=False)  # Nombre del archivo PDF
    source_link = Column(String)  # URL de Google Drive
    chunk_index = Column(Integer)  # Índice del chunk (0, 1, 2, ...)
    total_chunks = Column(Integer)  # Total de chunks del documento
    folder_id = Column(String, nullable=False)  # ID de la carpeta de Drive
    created_at = Column(DateTime, default=datetime.now)  # Timestamp de creación

# Inicializar sesión de base de datos (None si DATABASE_URL no está configurado)
SessionLocal = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(engine)  # Crear tablas si no existen
        SessionLocal = sessionmaker(bind=engine)
        logger.info("✓ Conexión a PostgreSQL establecida correctamente")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo conectar a PostgreSQL: {str(e)}")
        logger.warning("⚠️ Funcionando en modo sin persistencia (solo caché en memoria)")
else:
    logger.warning("⚠️ DATABASE_URL no configurado - persistencia deshabilitada")
    logger.warning("⚠️ Los embeddings se regenerarán en cada reinicio del servidor")

# ====================
# SISTEMA DE CACHÉ
# ====================
# Caché en memoria para archivos procesados
# Estructura: {"timestamp": datetime, "files_data": [...], "folder_id": "..."}
CACHE: Dict = {}
CACHE_TTL_HOURS = 24 * 365 * 100  # TTL infinito (~100 años)
# El caché solo se actualiza cuando:
# 1. El usuario llama a /api/refresh-cache (después de actualizar Drive)
# 2. Railway reinicia el servidor (llamar a /api/warmup manualmente)
# Esto garantiza CERO timeouts para los usuarios del GPT


def get_drive_service():
    """
    Conecta a Google Drive usando service account.
    Soporta credenciales desde variable de entorno o archivo.

    Returns:
        Resource: Servicio de Google Drive API
    """
    try:
        # Cargar credenciales desde base64 (Railway/producción) o archivo local (desarrollo)
        if GOOGLE_CREDENTIALS_BASE64:
            # Decodificar credenciales desde base64
            credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_BASE64).decode('utf-8')
            credentials_info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info, scopes=SCOPES
            )
            logger.info("✓ Credenciales cargadas desde GOOGLE_CREDENTIALS_BASE64")
        else:
            # Fallback a archivo local para desarrollo
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credenciales.json")
            if not os.path.exists(credentials_path):
                raise HTTPException(
                    status_code=500,
                    detail="No se encontraron credenciales. Configura GOOGLE_CREDENTIALS_BASE64 en Railway."
                )
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
            logger.info(f"✓ Credenciales cargadas desde archivo local: {credentials_path}")

        service = build('drive', 'v3', credentials=credentials)
        logger.info("✓ Conexión exitosa a Google Drive")
        return service
    except Exception as e:
        logger.error(f"✗ Error al conectar con Google Drive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al conectar con Google Drive: {str(e)}")


def is_cache_valid(folder_id: str) -> bool:
    """
    Verifica si el caché es válido para la carpeta especificada.

    Args:
        folder_id: ID de la carpeta de Google Drive

    Returns:
        bool: True si el caché es válido y no ha expirado
    """
    if not CACHE or CACHE.get("folder_id") != folder_id:
        return False

    cache_timestamp = CACHE.get("timestamp")
    if not cache_timestamp:
        return False

    # Verificar que el caché tenga contenido
    cached_files = CACHE.get("files_data", [])
    if not cached_files or len(cached_files) == 0:
        logger.warning(f"⚠️ Cache is empty (0 chunks), marking as invalid")
        return False

    # Verificar si el caché ha expirado (TTL)
    expiration_time = cache_timestamp + timedelta(hours=CACHE_TTL_HOURS)
    is_valid = datetime.now() < expiration_time

    if is_valid:
        time_left = (expiration_time - datetime.now()).total_seconds() / 60
        logger.info(f"📦 Caché válido - {len(cached_files)} chunks - Expira en {time_left:.1f} minutos")
    else:
        logger.info("🕐 Caché expirado - Se renovará")

    return is_valid


def get_cached_files() -> List[Dict]:
    """
    Obtiene los archivos del caché.

    Returns:
        List[Dict]: Lista de archivos procesados desde el caché
    """
    return CACHE.get("files_data", [])


def update_cache(folder_id: str, files_data: List[Dict]):
    """
    Actualiza el caché con nuevos datos de archivos.
    También persiste los datos en PostgreSQL si está configurado.

    Args:
        folder_id: ID de la carpeta de Google Drive
        files_data: Lista de diccionarios con información de archivos procesados
    """
    global CACHE
    CACHE = {
        "timestamp": datetime.now(),
        "folder_id": folder_id,
        "files_data": files_data,
        "total_files": len(files_data)
    }
    days = CACHE_TTL_HOURS / 24
    logger.info(f"💾 Caché actualizado: {len(files_data)} archivos - Válido por {days:.0f} día(s)")

    # Persistir en PostgreSQL (si está configurado)
    save_chunks_to_db(files_data, folder_id)


def invalidate_cache():
    """
    Invalida (limpia) el caché forzando una recarga en el próximo request.
    """
    global CACHE
    CACHE = {}
    logger.info("🗑️ Caché invalidado - Se renovará en el próximo request")


# ====================
# FUNCIONES DE PERSISTENCIA (PostgreSQL)
# ====================

def save_chunks_to_db(chunks: List[Dict], folder_id: str):
    """
    Guarda chunks con embeddings en PostgreSQL en lotes pequeños.
    Primero borra los chunks existentes del folder_id, luego inserta los nuevos.

    Args:
        chunks: Lista de diccionarios con chunks y embeddings
        folder_id: ID de la carpeta de Google Drive
    """
    if not SessionLocal:
        logger.warning("⚠️ PostgreSQL no configurado - no se persistirán embeddings")
        return

    BATCH_SIZE = 50  # Insertar en lotes de 50 para evitar timeouts

    try:
        db: Session = SessionLocal()

        # Borrar chunks antiguos del mismo folder_id
        deleted_count = db.query(DocumentChunk).filter(
            DocumentChunk.folder_id == folder_id
        ).delete()
        db.commit()

        if deleted_count > 0:
            logger.info(f"🗑️  Borrados {deleted_count} chunks antiguos de la base de datos")

        # Filtrar chunks con embedding válido
        valid_chunks = [c for c in chunks if c.get('embedding') is not None]
        total_saved = 0

        # Insertar en lotes
        for i in range(0, len(valid_chunks), BATCH_SIZE):
            batch = valid_chunks[i:i + BATCH_SIZE]

            for chunk_data in batch:
                db_chunk = DocumentChunk(
                    chunk_id=chunk_data['chunk_id'],
                    text=chunk_data['text'],
                    embedding=chunk_data['embedding'],
                    source_document=chunk_data['source_document'],
                    source_link=chunk_data.get('source_link', ''),
                    chunk_index=chunk_data.get('chunk_index', 0),
                    total_chunks=chunk_data.get('total_chunks', 1),
                    folder_id=folder_id
                )
                db.add(db_chunk)

            db.commit()
            total_saved += len(batch)
            logger.info(f"💾 Lote guardado: {total_saved}/{len(valid_chunks)} chunks")

        logger.info(f"💾 Guardados {total_saved} chunks en PostgreSQL")
        db.close()

    except Exception as e:
        logger.error(f"✗ Error al guardar chunks en PostgreSQL: {str(e)}")
        try:
            db.rollback()
            db.close()
        except Exception:
            pass


def load_chunks_from_db(folder_id: str) -> List[Dict]:
    """
    Carga chunks con embeddings desde PostgreSQL.

    Args:
        folder_id: ID de la carpeta de Google Drive

    Returns:
        List[Dict]: Lista de chunks en formato dict (compatible con CACHE)
    """
    if not SessionLocal:
        return []

    try:
        db: Session = SessionLocal()

        db_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.folder_id == folder_id
        ).all()

        chunks = []
        for db_chunk in db_chunks:
            chunks.append({
                'chunk_id': db_chunk.chunk_id,
                'text': db_chunk.text,
                'embedding': db_chunk.embedding,  # JSONB → list automáticamente
                'source_document': db_chunk.source_document,
                'source_link': db_chunk.source_link,
                'chunk_index': db_chunk.chunk_index,
                'total_chunks': db_chunk.total_chunks
            })

        db.close()

        if chunks:
            logger.info(f"✓ Cargados {len(chunks)} chunks desde PostgreSQL")

        return chunks

    except Exception as e:
        logger.error(f"✗ Error al cargar chunks desde PostgreSQL: {str(e)}")
        if db:
            db.close()
        return []


def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extrae texto de un archivo PDF.

    Args:
        file_content: Contenido del archivo PDF en bytes

    Returns:
        str: Texto extraído del PDF
    """
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"

        return text.strip()
    except Exception as e:
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        return f"[Error al extraer texto del PDF: {str(e)}]"


def extract_text_from_docx(file_content: bytes) -> str:
    """
    Extrae texto de un archivo DOCX.

    Args:
        file_content: Contenido del archivo DOCX en bytes

    Returns:
        str: Texto extraído del DOCX
    """
    try:
        docx_file = io.BytesIO(file_content)
        doc = Document(docx_file)
        text = ""

        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"

        return text.strip()
    except Exception as e:
        logger.error(f"Error al extraer texto del DOCX: {str(e)}")
        return f"[Error al extraer texto del DOCX: {str(e)}]"


def download_file(service, file_id: str) -> bytes:
    """
    Descarga un archivo de Google Drive.

    Args:
        service: Servicio de Google Drive API
        file_id: ID del archivo en Google Drive

    Returns:
        bytes: Contenido del archivo
    """
    try:
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        file_buffer.seek(0)
        return file_buffer.read()
    except Exception as e:
        logger.error(f"Error al descargar archivo {file_id}: {str(e)}")
        raise


def list_files_in_folder(service, folder_id: str, search_term: Optional[str] = None):
    """
    Lista archivos de una carpeta de Google Drive.

    IMPORTANTE: Ya no filtra por término de búsqueda en Drive API.
    Ahora descarga TODOS los archivos y la búsqueda se hace localmente.

    Args:
        service: Servicio de Google Drive API
        folder_id: ID de la carpeta en Google Drive
        search_term: Término de búsqueda opcional (solo para búsqueda en nombre de archivo)

    Returns:
        list: Lista de archivos encontrados
    """
    try:
        # Solo buscar por carpeta padre y archivos no eliminados
        # Removida búsqueda fullText porque no funciona bien con documentos grandes
        query = f"'{folder_id}' in parents and trashed=false"

        # Opcionalmente buscar solo en el nombre (más rápido para filtrado inicial)
        if search_term:
            # Buscar solo en nombre para filtrado inicial rápido
            query += f" and name contains '{search_term}'"
            logger.info(f"Buscando archivos con '{search_term}' en el nombre")

        results = service.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType, webViewLink, size, modifiedTime)"
        ).execute()

        files = results.get('files', [])
        logger.info(f"Se encontraron {len(files)} archivos en Drive")
        return files
    except Exception as e:
        logger.error(f"Error al listar archivos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")


# ====================
# FUNCIONES DE BÚSQUEDA SEMÁNTICA
# ====================

def split_text_into_chunks(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Divide texto en chunks semánticos basados en párrafos.

    Args:
        text: Texto completo a dividir
        chunk_size: Tamaño aproximado de cada chunk en caracteres
        overlap: Cantidad de caracteres de solapamiento entre chunks

    Returns:
        List[str]: Lista de chunks de texto
    """
    if not text or len(text.strip()) == 0:
        return []

    # Dividir por párrafos (doble salto de línea o salto simple)
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        # Si agregar este párrafo excede el tamaño, guardar chunk actual
        if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Mantener overlap tomando últimos N caracteres
            current_chunk = current_chunk[-overlap:] + " " if overlap > 0 else ""

        current_chunk += paragraph + " "

    # Agregar último chunk si no está vacío
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def generate_embedding(text: str) -> List[float]:
    """
    Genera embedding de un texto usando OpenAI API.

    Args:
        text: Texto a convertir en embedding

    Returns:
        List[float]: Vector de embedding (1536 dimensiones)
    """
    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API no configurado. Agrega OPENAI_API_KEY en variables de entorno."
        )

    try:
        # Truncar texto si es muy largo (max 8191 tokens para text-embedding-3-small)
        max_chars = 30000  # ~8000 tokens aproximadamente
        if len(text) > max_chars:
            text = text[:max_chars]

        response = openai_client.embeddings.create(
            model="text-embedding-3-small",  # Más barato y rápido
            input=text
        )

        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error al generar embedding: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar embedding: {str(e)}")


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calcula similitud coseno entre dos vectores.

    Args:
        vec1: Primer vector
        vec2: Segundo vector

    Returns:
        float: Similitud coseno (0 a 1)
    """
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def semantic_search(query: str, chunks_data: List[Dict], top_k: int = 10) -> List[Dict]:
    """
    Busca chunks más relevantes usando similitud semántica.

    Args:
        query: Consulta del usuario
        chunks_data: Lista de chunks con embeddings
        top_k: Número de resultados a retornar

    Returns:
        List[Dict]: Top K chunks más similares ordenados por relevancia
    """
    # Generar embedding de la consulta
    query_embedding = generate_embedding(query)

    # Calcular similitud con cada chunk
    results = []
    for chunk in chunks_data:
        similarity = cosine_similarity(query_embedding, chunk['embedding'])
        results.append({
            **chunk,
            'similarity': similarity
        })

    # Ordenar por similitud descendente y tomar top K
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]


def normalize_text(text: str) -> str:
    """
    Normaliza texto: convierte a minúsculas y remueve tildes.

    Args:
        text: Texto a normalizar

    Returns:
        str: Texto normalizado
    """
    # Convertir a minúsculas
    text = text.lower()
    # Remover tildes
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text


def format_response(files_data: list) -> str:
    """
    Formatea la respuesta en el formato especificado (OBSOLETO - usar format_chunks_response).

    Args:
        files_data: Lista de diccionarios con información de archivos

    Returns:
        str: Respuesta formateada como string
    """
    response_parts = []

    for file_data in files_data:
        file_info = f"📄 **{file_data['name']}**\n"
        file_info += f"🔗 {file_data['link']}\n"
        file_info += f"CONTENIDO:\n{file_data['content']}\n"

        # Agregar nota si el contenido fue truncado
        if file_data.get('was_truncated', False):
            file_info += f"\n⚠️ **Nota:** El contenido fue truncado a 30,000 caracteres. Para ver el documento completo: {file_data['link']}\n"

        file_info += "=" * 40 + "\n"
        response_parts.append(file_info)

    return "\n".join(response_parts)


def format_chunks_response(chunks: List[Dict]) -> str:
    """
    Formatea chunks encontrados por búsqueda semántica.

    Args:
        chunks: Lista de chunks con información de similitud

    Returns:
        str: Respuesta formateada como string
    """
    response_parts = []

    for i, chunk in enumerate(chunks, 1):
        chunk_info = f"📄 **{chunk['source_document']}**"

        # Agregar información de similitud si está disponible
        if 'similarity' in chunk:
            chunk_info += f" (Relevancia: {chunk['similarity']:.2%})"

        chunk_info += f"\n🔗 {chunk['source_link']}\n"
        chunk_info += f"📍 Sección {chunk['chunk_index'] + 1} de {chunk['total_chunks']}\n\n"
        chunk_info += f"{chunk['text']}\n"
        chunk_info += "=" * 60 + "\n"

        response_parts.append(chunk_info)

    return "\n".join(response_parts)


# ====================
# EVENTOS DEL SERVIDOR
# ====================

@app.on_event("startup")
async def startup_event():
    """
    Evento que se ejecuta al iniciar el servidor.
    Carga el caché desde PostgreSQL si está disponible.
    """
    logger.info("🚀 Iniciando servidor FastAPI...")

    if not DATABASE_URL or not SessionLocal:
        logger.warning("⚠️ PostgreSQL no configurado - caché no se cargará automáticamente")
        return

    if not FOLDER_ID:
        logger.warning("⚠️ FOLDER_ID no configurado - no se puede cargar caché")
        return

    # Intentar cargar chunks desde PostgreSQL
    logger.info("📥 Intentando cargar caché desde PostgreSQL...")
    chunks = load_chunks_from_db(FOLDER_ID)

    if chunks:
        # Actualizar caché en memoria (sin persistir de nuevo en DB)
        global CACHE
        CACHE = {
            "timestamp": datetime.now(),
            "folder_id": FOLDER_ID,
            "files_data": chunks,
            "total_files": len(chunks)
        }
        logger.info(f"✅ Caché cargado exitosamente: {len(chunks)} chunks desde PostgreSQL")
        logger.info(f"   Servicio listo para búsquedas instantáneas sin regenerar embeddings")
    else:
        logger.info("📭 No hay chunks en PostgreSQL - será necesario ejecutar /api/refresh-cache")


@app.get("/")
async def root():
    """Endpoint raíz para verificar que la API está funcionando."""
    cache_status = "warm" if is_cache_valid(FOLDER_ID) else "cold"
    cache_files = len(get_cached_files()) if is_cache_valid(FOLDER_ID) else 0

    return {
        "message": "API de Normativas EGESUR",
        "status": "online",
        "cache_status": cache_status,
        "cache_files": cache_files,
        "cache_ttl_days": CACHE_TTL_HOURS / 24,
        "endpoints": {
            "/api/buscarNormativa": "Buscar normativas en Google Drive",
            "/api/warmup": "Precargar caché (útil después de deployment)",
            "/api/refresh-cache": "Actualizar caché cuando se modifica la base de conocimiento"
        }
    }


@app.get("/ping", include_in_schema=False)
async def health_ping():
    """Endpoint mínimo para mantener despierto el servicio (cron ping)."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/debug/env")
async def debug_env():
    """Endpoint de diagnóstico para verificar variables de entorno."""
    return {
        "FOLDER_ID": "configured" if FOLDER_ID else "missing",
        "GOOGLE_CREDENTIALS_BASE64": "configured" if GOOGLE_CREDENTIALS_BASE64 else "missing",
        "OPENAI_API_KEY": "configured" if OPENAI_API_KEY else "missing",
        "openai_client_status": "initialized" if openai_client else "not_initialized"
    }


@app.get("/api/debug/test-drive")
async def debug_test_drive():
    """Endpoint de debug para verificar conexión con Google Drive."""
    try:
        service = get_drive_service()
        files = list_files_in_folder(service, FOLDER_ID, search_term=None)

        file_info = []
        for f in files[:5]:  # Solo primeros 5 archivos
            file_info.append({
                "name": f['name'],
                "mimeType": f['mimeType'],
                "id": f['id']
            })

        return {
            "success": True,
            "total_files": len(files),
            "sample_files": file_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/debug/cache-status")
async def debug_cache_status():
    """Endpoint de debug para verificar el estado del caché."""
    global CACHE

    if not CACHE:
        return {
            "cache_exists": False,
            "message": "Cache is empty"
        }

    cached_files = CACHE.get("files_data", [])
    cache_timestamp = CACHE.get("timestamp")

    return {
        "cache_exists": True,
        "folder_id": CACHE.get("folder_id"),
        "timestamp": cache_timestamp.isoformat() if cache_timestamp else None,
        "total_chunks": len(cached_files),
        "is_valid": is_cache_valid(FOLDER_ID),
        "ttl_hours": CACHE_TTL_HOURS,
        "sample_chunks": [
            {
                "source": chunk.get("source_document", "unknown"),
                "chunk_index": chunk.get("chunk_index", 0),
                "text_preview": chunk.get("text", "")[:100] + "..."
            }
            for chunk in cached_files[:3]
        ] if cached_files else []
    }


@app.post("/api/debug/clear-cache")
async def debug_clear_cache():
    """Endpoint de debug para limpiar el caché forzosamente."""
    global CACHE
    CACHE = {}
    return {
        "success": True,
        "message": "Cache cleared successfully"
    }


@app.get("/api/debug/test-openai")
async def debug_test_openai():
    """Test OpenAI API connection and embedding generation."""
    try:
        if not openai_client:
            return {
                "success": False,
                "error": "OpenAI client not initialized",
                "api_key_configured": bool(OPENAI_API_KEY)
            }

        # Test simple embedding
        test_text = "Esta es una prueba de generación de embeddings para EGESUR."

        logger.info(f"Testing OpenAI API with text: {test_text[:50]}...")

        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text
        )

        embedding = response.data[0].embedding

        return {
            "success": True,
            "message": "OpenAI API working correctly",
            "embedding_dimensions": len(embedding),
            "embedding_preview": embedding[:5],
            "model": "text-embedding-3-small",
            "api_key_configured": True
        }

    except Exception as e:
        logger.error(f"OpenAI API test failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "api_key_configured": bool(OPENAI_API_KEY)
        }


@app.get("/api/warmup")
async def warmup_cache():
    """
    Precarga el caché con todos los archivos de Google Drive.

    Este endpoint debe ser llamado después del despliegue en Railway
    para evitar que la primera consulta del GPT haga timeout.

    Returns:
        dict: Estado de la precarga del caché
    """
    try:
        # Verificar configuración
        if not FOLDER_ID:
            raise HTTPException(
                status_code=500,
                detail="FOLDER_ID no configurado. Verifica el archivo .env"
            )

        # Verificar que OpenAI client esté configurado
        if not openai_client:
            logger.error("❌ OPENAI_API_KEY no está configurado o es inválido")
            raise HTTPException(
                status_code=500,
                detail="OpenAI API no configurado. Verifica que OPENAI_API_KEY esté en las variables de entorno."
            )

        # Si el caché ya está válido, no hacer nada
        if is_cache_valid(FOLDER_ID):
            cached_chunks = get_cached_files()
            unique_docs = len(set(chunk.get('source_document', '') for chunk in cached_chunks if 'source_document' in chunk))
            return {
                "success": True,
                "message": "Caché ya está precargado y válido",
                "total_chunks": len(cached_chunks),
                "total_documents": unique_docs,
                "cache_status": "warm"
            }

        # Precargar caché
        logger.info("🔥 Iniciando precarga de caché...")

        # Conectar a Google Drive
        service = get_drive_service()

        # Listar TODOS los archivos
        logger.info(f"Listando archivos de la carpeta {FOLDER_ID}")
        files = list_files_in_folder(service, FOLDER_ID, search_term=None)
        logger.info(f"Total de archivos encontrados: {len(files) if files else 0}")

        if not files:
            return {
                "success": False,
                "message": "No hay archivos en la carpeta para precargar",
                "total_files": 0,
                "cache_status": "empty"
            }

        logger.info(f"Precargando {len(files)} archivos...")
        logger.info(f"Archivos a procesar: {[f['name'] for f in files]}")

        # Procesar archivos y extraer contenido
        all_files_data = []
        embedding_errors = []  # Track embedding errors

        for file in files:
            file_id = file['id']
            file_name = file['name']
            mime_type = file['mimeType']
            web_link = file.get('webViewLink', 'No disponible')

            logger.info(f"Procesando archivo: {file_name} ({mime_type})")

            content = ""

            try:
                if mime_type == 'application/pdf':
                    logger.info(f"  → Descargando PDF...")
                    file_content = download_file(service, file_id)
                    logger.info(f"  → Tamaño descargado: {len(file_content)} bytes")
                    content = extract_text_from_pdf(file_content)
                    logger.info(f"  → Texto extraído: {len(content)} caracteres")
                elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                    logger.info(f"  → Descargando DOCX...")
                    file_content = download_file(service, file_id)
                    logger.info(f"  → Tamaño descargado: {len(file_content)} bytes")
                    content = extract_text_from_docx(file_content)
                    logger.info(f"  → Texto extraído: {len(content)} caracteres")
                elif mime_type == 'application/vnd.google-apps.document':
                    logger.info(f"  → Exportando Google Doc...")
                    request = service.files().export_media(
                        fileId=file_id,
                        mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    )
                    file_buffer = io.BytesIO()
                    downloader = MediaIoBaseDownload(file_buffer, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    file_buffer.seek(0)
                    buffer_content = file_buffer.read()
                    logger.info(f"  → Tamaño exportado: {len(buffer_content)} bytes")
                    content = extract_text_from_docx(buffer_content)
                    logger.info(f"  → Texto extraído: {len(content)} caracteres")
                else:
                    content = f"[Tipo de archivo no soportado: {mime_type}]"
                    logger.warning(f"Tipo de archivo no soportado: {mime_type} para {file_name}")

                # Dividir contenido en chunks y generar embeddings
                logger.info(f"  → Dividiendo en chunks y generando embeddings...")
                chunks = split_text_into_chunks(content, chunk_size=3000, overlap=300)
                logger.info(f"  → Se generaron {len(chunks)} chunks")

                for i, chunk_text in enumerate(chunks):
                    try:
                        embedding = generate_embedding(chunk_text)
                        all_files_data.append({
                            'chunk_id': f"{file_id}_{i}",
                            'text': chunk_text,
                            'embedding': embedding,
                            'source_document': file_name,
                            'source_link': web_link,
                            'chunk_index': i,
                            'total_chunks': len(chunks)
                        })
                    except Exception as embed_error:
                        error_msg = f"{file_name} chunk {i}: {str(embed_error)}"
                        logger.error(f"  ✗ Error al generar embedding: {error_msg}")
                        embedding_errors.append(error_msg)

                logger.info(f"  ✓ Generados {len(chunks)} chunks con embeddings para {file_name}")

            except Exception as e:
                logger.error(f"Error al procesar archivo {file_name}: {str(e)}")
                # Agregar un chunk de error
                all_files_data.append({
                    'chunk_id': f"{file_id}_error",
                    'text': f"[Error al procesar archivo: {str(e)}]",
                    'embedding': None,
                    'source_document': file_name,
                    'source_link': web_link,
                    'chunk_index': 0,
                    'total_chunks': 1
                })

        # Actualizar caché
        update_cache(FOLDER_ID, all_files_data)

        logger.info("🔥 Precarga de caché completada exitosamente")

        # Contar documentos únicos
        unique_docs = len(set(chunk['source_document'] for chunk in all_files_data if 'source_document' in chunk))

        result = {
            "success": True if len(all_files_data) > 0 else False,
            "message": "Caché precargado exitosamente con embeddings" if len(all_files_data) > 0 else "Error: No se generaron embeddings",
            "total_chunks": len(all_files_data),
            "total_documents": unique_docs,
            "cache_status": "warm",
            "cache_ttl_hours": CACHE_TTL_HOURS
        }

        # Include embedding errors if any occurred
        if embedding_errors:
            result["embedding_errors"] = embedding_errors[:5]  # Show first 5 errors
            result["total_errors"] = len(embedding_errors)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en precarga de caché: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en precarga de caché: {str(e)}")


@app.post("/api/refresh-cache")
async def refresh_cache():
    """
    Invalida el caché actual y fuerza una recarga completa desde Google Drive.

    Este endpoint debe ser llamado cuando se actualiza la base de conocimiento en Drive
    (ej: cuando se sube una nueva normativa o se modifica un documento existente).

    Returns:
        dict: Resultado de la actualización del caché
    """
    try:
        logger.info("🔄 Solicitud de actualización de caché recibida")

        # Invalidar caché actual
        invalidate_cache()

        # Llamar a warmup para recargar inmediatamente
        result = await warmup_cache()

        return {
            "success": True,
            "message": "Caché actualizado exitosamente con embeddings generados",
            "total_chunks": result.get("total_chunks", 0),
            "total_documents": result.get("total_documents", 0),
            "cache_status": "refreshed",
            "cache_ttl_days": CACHE_TTL_HOURS / 24
        }

    except Exception as e:
        logger.error(f"Error al actualizar caché: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar caché: {str(e)}")


@app.get("/api/buscarNormativa")
async def buscar_normativa(termino: Optional[str] = Query(None, description="Término de búsqueda opcional")):
    """
    Busca normativas en Google Drive y retorna su contenido.

    ESTRATEGIA DE BÚSQUEDA MEJORADA CON CACHÉ:
    1. Verifica si existe caché válido (< 1 hora)
    2. Si hay caché: Usa archivos en memoria (5-10 segundos)
    3. Si no hay caché: Descarga todos los archivos y los guarda en caché (2-3 minutos)
    4. Filtra localmente por término de búsqueda

    Args:
        termino: Término de búsqueda opcional para filtrar archivos

    Returns:
        dict: Respuesta con el contenido de los archivos encontrados
    """
    try:
        # Verificar configuración
        if not FOLDER_ID:
            raise HTTPException(
                status_code=500,
                detail="FOLDER_ID no configurado. Verifica el archivo .env"
            )

        # ====================
        # VERIFICAR CACHÉ
        # ====================
        if is_cache_valid(FOLDER_ID):
            # Usar caché existente (RÁPIDO)
            logger.info("⚡ Usando archivos desde caché")
            all_files_data = get_cached_files()
        else:
            # Renovar caché (LENTO - primera vez o después de 1 hora)
            logger.info("🔄 Caché no disponible - Descargando archivos de Drive...")

            # Conectar a Google Drive
            service = get_drive_service()

            # Listar TODOS los archivos (sin filtro de búsqueda en Drive API)
            logger.info(f"Listando archivos de la carpeta {FOLDER_ID}")
            files = list_files_in_folder(service, FOLDER_ID, search_term=None)

            if not files:
                return {
                    "success": True,
                    "message": "No se encontraron archivos en la carpeta",
                    "total_files": 0,
                    "content": "No se encontraron archivos en la carpeta de Google Drive."
                }

            logger.info(f"Descargados {len(files)} archivos. Procesando contenido...")

            # Procesar archivos y extraer contenido
            all_files_data = []

            for file in files:
                file_id = file['id']
                file_name = file['name']
                mime_type = file['mimeType']
                web_link = file.get('webViewLink', 'No disponible')

                logger.info(f"Procesando archivo: {file_name} ({mime_type})")

                # Extraer contenido según tipo de archivo
                content = ""

                try:
                    if mime_type == 'application/pdf':
                        file_content = download_file(service, file_id)
                        content = extract_text_from_pdf(file_content)
                    elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                        file_content = download_file(service, file_id)
                        content = extract_text_from_docx(file_content)
                    elif mime_type == 'application/vnd.google-apps.document':
                        # Exportar Google Docs como DOCX y extraer texto
                        request = service.files().export_media(
                            fileId=file_id,
                            mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        )
                        file_buffer = io.BytesIO()
                        downloader = MediaIoBaseDownload(file_buffer, request)
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                        file_buffer.seek(0)
                        content = extract_text_from_docx(file_buffer.read())
                    else:
                        content = f"[Tipo de archivo no soportado: {mime_type}]"
                        logger.warning(f"Tipo de archivo no soportado: {mime_type} para {file_name}")

                    # Dividir contenido en chunks y generar embeddings
                    logger.info(f"  → Dividiendo en chunks y generando embeddings...")
                    chunks = split_text_into_chunks(content, chunk_size=3000, overlap=300)

                    for i, chunk_text in enumerate(chunks):
                        try:
                            embedding = generate_embedding(chunk_text)
                            all_files_data.append({
                                'chunk_id': f"{file_id}_{i}",
                                'text': chunk_text,
                                'embedding': embedding,
                                'source_document': file_name,
                                'source_link': web_link,
                                'chunk_index': i,
                                'total_chunks': len(chunks)
                            })
                        except Exception as embed_error:
                            logger.error(f"  ✗ Error al generar embedding para chunk {i}: {str(embed_error)}")

                    logger.info(f"  ✓ Generados {len(chunks)} chunks con embeddings para {file_name}")

                except Exception as e:
                    logger.error(f"Error al procesar archivo {file_name}: {str(e)}")
                    # Agregar un chunk de error
                    all_files_data.append({
                        'chunk_id': f"{file_id}_error",
                        'text': f"[Error al procesar archivo: {str(e)}]",
                        'embedding': None,
                        'source_document': file_name,
                        'source_link': web_link,
                        'chunk_index': 0,
                        'total_chunks': 1
                    })

            # Actualizar caché con todos los archivos procesados
            update_cache(FOLDER_ID, all_files_data)

        # ====================
        # BÚSQUEDA SEMÁNTICA
        # ====================
        MAX_CHUNKS_IN_RESPONSE = 10  # Número de chunks más relevantes a retornar

        if termino:
            # Filtrar chunks que tienen embeddings válidos
            chunks_with_embeddings = [c for c in all_files_data if c.get('embedding') is not None]

            if not chunks_with_embeddings:
                return {
                    "success": False,
                    "message": "No hay embeddings disponibles. Verifica que OPENAI_API_KEY esté configurado.",
                    "total_chunks": 0,
                    "search_term": termino,
                    "content": "Error: No se pudieron generar embeddings para la búsqueda."
                }

            # Búsqueda semántica
            logger.info(f"🔍 Buscando semánticamente: '{termino}' en {len(chunks_with_embeddings)} chunks")
            top_chunks = semantic_search(termino, chunks_with_embeddings, top_k=MAX_CHUNKS_IN_RESPONSE)

            if not top_chunks:
                return {
                    "success": True,
                    "message": "No se encontraron resultados relevantes",
                    "total_chunks": 0,
                    "search_term": termino,
                    "content": f"No se encontraron chunks relevantes para '{termino}'."
                }

            logger.info(f"✓ Encontrados {len(top_chunks)} chunks relevantes")
            for i, chunk in enumerate(top_chunks[:5]):  # Log solo top 5
                logger.info(f"  {i+1}. {chunk['source_document']} (similitud: {chunk['similarity']:.3f})")

        else:
            # Sin término de búsqueda, retornar primeros N chunks
            top_chunks = all_files_data[:MAX_CHUNKS_IN_RESPONSE]

        # Formatear respuesta con chunks
        formatted_content = format_chunks_response(top_chunks)

        total_chunks = len(top_chunks)
        logger.info(f"✓ Búsqueda completada: Retornando {total_chunks} chunk(s) más relevantes")

        return {
            "success": True,
            "message": f"Se encontraron {total_chunks} sección(es) relevante(s)",
            "total_chunks": total_chunks,
            "search_term": termino,
            "content": formatted_content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
