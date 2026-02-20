# Schema OpenAPI para GPT Custom Actions

Este es el schema que debes copiar y pegar en la configuración de Custom Actions de tu GPT en ChatGPT.

## Instrucciones de uso:

1. Ve a tu GPT en ChatGPT
2. Sección "Actions" → "Create new action"
3. Copia y pega el siguiente schema completo
4. Guarda los cambios

---

```yaml
openapi: 3.1.0
info:
  title: API de Normativas EGESUR
  description: API para consultar normativas y documentos técnicos de EGESUR almacenados en Google Drive. Incluye sistema de caché de 7 días para respuestas rápidas.
  version: 2.0.0
servers:
  - url: https://TU-URL.onrender.com
    description: Servidor de producción en Render

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer

security:
  - BearerAuth: []

paths:
  /api/buscarNormativa:
    get:
      operationId: buscarNormativa
      summary: Buscar normativas en Google Drive
      description: Busca y recupera el contenido completo de documentos normativos de EGESUR. Si no se proporciona término de búsqueda, retorna todos los documentos disponibles.
      parameters:
        - name: termino
          in: query
          description: Término de búsqueda para filtrar documentos por nombre o contenido (opcional)
          required: false
          schema:
            type: string
            example: "emergencia"
      responses:
        '200':
          description: Búsqueda exitosa
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    description: Indica si la operación fue exitosa
                  message:
                    type: string
                    description: Mensaje descriptivo del resultado
                  total_files:
                    type: integer
                    description: Número de archivos encontrados
                  search_term:
                    type: string
                    nullable: true
                    description: Término de búsqueda utilizado
                  content:
                    type: string
                    description: Contenido completo de los documentos encontrados en formato texto
              example:
                success: true
                message: "Se encontraron 3 archivo(s)"
                total_files: 3
                search_term: "emergencia"
                content: "📄 **Directiva de Adquisiciones de Emergencia EGESUR**\n🔗 https://docs.google.com/document/d/xxx\nCONTENIDO:\n[texto del documento]\n========================================"
        '500':
          description: Error del servidor
          content:
            application/json:
              schema:
                type: object
                properties:
                  detail:
                    type: string
                    description: Descripción del error

  /api/refresh-cache:
    post:
      operationId: refreshCache
      summary: Actualizar caché de normativas
      description: Invalida el caché actual y recarga todos los documentos desde Google Drive. Usar cuando se sube, modifica o elimina documentos. Proceso tarda 2-3 minutos.
      responses:
        '200':
          description: Caché actualizado exitosamente
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    description: Indica si la operación fue exitosa
                  message:
                    type: string
                    description: Mensaje descriptivo del resultado
                  total_files:
                    type: integer
                    description: Número total de archivos en el caché actualizado
                  cache_status:
                    type: string
                    description: Estado del caché después de la actualización
                    enum: [refreshed]
                  cache_ttl_days:
                    type: number
                    description: Días de validez del caché (normalmente 7)
              example:
                success: true
                message: "Caché actualizado exitosamente con los últimos documentos de Google Drive"
                total_files: 17
                cache_status: "refreshed"
                cache_ttl_days: 7
        '500':
          description: Error del servidor
          content:
            application/json:
              schema:
                type: object
                properties:
                  detail:
                    type: string
                    description: Descripción del error
```

---

## Endpoints disponibles:

### 1. GET /api/buscarNormativa
Busca documentos normativos por término de búsqueda.

**Parámetros:**
- `termino` (opcional): Texto a buscar en los documentos

**Uso típico:**
- El GPT llama este endpoint con términos como "licitación", "obras", "bienes", etc.
- Retorna documentos filtrados que contienen esos términos

### 2. POST /api/refresh-cache
Actualiza la base de conocimiento después de modificar documentos en Google Drive.

**Cuándo usar:**
- Cuando el usuario sube nuevos documentos
- Cuando se modifican documentos existentes
- Cuando se eliminan documentos

**Nota:** Tarda 2-3 minutos en completarse.

---

## Configuración adicional en el GPT:

- **Authentication:** API Key
  - **Auth Type:** Bearer
  - **API Key:** (pegar la misma API_KEY configurada en Render)
- **Privacy:** Según tus necesidades (Private/Company/Public)
