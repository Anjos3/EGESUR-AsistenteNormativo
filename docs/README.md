# API de Normativas EGESUR

API REST para consultar normativas y documentos técnicos de EGESUR almacenados en Google Drive.

## Características

- Búsqueda de documentos normativos por término
- Extracción automática de texto de PDF, DOCX y Google Docs
- Integración con ChatGPT Custom Actions
- CORS habilitado

## Endpoints

### `GET /api/buscarNormativa`

Busca y retorna el contenido de documentos normativos.

**Parámetros:**
- `termino` (opcional): Término de búsqueda para filtrar documentos

**Ejemplo:**
```bash
GET /api/buscarNormativa?termino=emergencia
```

## Despliegue en Railway

### Variables de entorno requeridas:

1. `FOLDER_ID` - ID de la carpeta de Google Drive
2. `GOOGLE_APPLICATION_CREDENTIALS` - Nombre del archivo de credenciales (por defecto: `credenciales.json`)

### Archivo de credenciales:

El archivo `credenciales.json` debe subirse manualmente a Railway después del despliegue.

## Tecnologías

- FastAPI
- Google Drive API
- PyPDF2
- python-docx
