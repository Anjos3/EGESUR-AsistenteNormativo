# Configuración de PostgreSQL para Persistencia de Embeddings

## ¿Por qué PostgreSQL?

**Problema:** Render (plan gratuito) duerme el servicio después de 15 minutos de inactividad. Al despertar, la caché en memoria se pierde y los embeddings deben regenerarse (~10 minutos para 17 PDFs).

**Solución:** Almacenar embeddings en PostgreSQL. Al reiniciar, el servidor carga los embeddings desde la base de datos en 2-5 segundos, evitando regeneración.

**Ventajas:**
- ✅ Embeddings persisten entre reinicios
- ✅ Startup rápido (2-5 segundos vs 10+ minutos)
- ✅ Plan gratuito de Render PostgreSQL: 256 MB (suficiente para ~50 PDFs)
- ✅ Sin dependencia de pgvector (funciona con JSONB estándar)

---

## Paso 1: Crear Base de Datos PostgreSQL en Render

### 1.1 Acceder al Dashboard de Render

1. Ve a https://dashboard.render.com
2. Inicia sesión con tu cuenta

### 1.2 Crear Nueva Base de Datos

1. Click en **"New +"** (botón azul arriba a la derecha)
2. Selecciona **"PostgreSQL"**

### 1.3 Configurar la Base de Datos

Completa el formulario con estos valores:

- **Name:** `egesur-embeddings-db` (o el nombre que prefieras)
- **Database:** `egesur_db` (nombre interno de la base de datos)
- **User:** `egesur_user` (se genera automáticamente)
- **Region:** Selecciona la misma región que tu servicio web (ej: `Oregon (US West)`)
- **PostgreSQL Version:** `16` (o la más reciente disponible)
- **Plan Type:** **Free** (256 MB, expira en 90 días)

4. Click en **"Create Database"**

⏱️ La creación toma 2-3 minutos. Espera a que el estado cambie a **"Available"**.

---

## Paso 2: Obtener la URL de Conexión

### 2.1 Copiar Internal Database URL

1. Una vez creada la base de datos, verás la página de detalles
2. Busca la sección **"Connections"**
3. Copia la **"Internal Database URL"** (empieza con `postgresql://`)

**Ejemplo:**
```
postgresql://egesur_user:abc123xyz@dpg-abcd1234567890-a/egesur_db
```

> ⚠️ **Importante:** Usa la **Internal Database URL**, no la External. Es más rápida y gratuita.

---


## Paso 3: Configurar Variable de Entorno en Render

### 3.1 Acceder a tu Servicio Web

1. Ve a https://dashboard.render.com
2. Click en tu servicio **"egesur"** (o como lo hayas nombrado)

### 3.2 Agregar Variable de Entorno

1. En el menú lateral, click en **"Environment"**
2. Click en **"Add Environment Variable"**
3. Completa:
   - **Key:** `DATABASE_URL`
   - **Value:** Pega la URL que copiaste en el Paso 2.1

**Ejemplo:**
```
Key:   DATABASE_URL
Value: postgresql://egesur_user:abc123xyz@dpg-abcd1234567890-a/egesur_db
```

4. Click en **"Save Changes"**

### 3.3 Redesplegar el Servicio

Render detectará el cambio automáticamente y redesplegará el servicio. Espera 2-3 minutos.

---

## Paso 4: Verificar la Conexión

### 4.1 Ver Logs del Despliegue

1. En tu servicio, ve a la pestaña **"Logs"**
2. Busca estos mensajes al inicio:

```
✓ OpenAI API configurado correctamente para embeddings
✓ Conexión a PostgreSQL establecida correctamente
🚀 Iniciando servidor FastAPI...
📥 Intentando cargar caché desde PostgreSQL...
```

**Si ves esto, la conexión fue exitosa.** ✅

**Si ves errores:**
- ❌ `⚠️ No se pudo conectar a PostgreSQL`: Verifica que la `DATABASE_URL` esté correcta
- ❌ `📭 No hay chunks en PostgreSQL`: Normal en el primer despliegue (continúa al Paso 5)

---

## Paso 5: Poblar la Base de Datos con Embeddings

### 5.1 Ejecutar Refresh Cache

Una vez que el servicio esté en línea, ejecuta el endpoint de refresh:

```bash
curl -X POST "https://egesur.onrender.com/api/refresh-cache"
```

⏱️ Este proceso tomará **10-15 minutos** (solo la primera vez) porque:
1. Descarga los 17 PDFs de Google Drive
2. Genera embeddings con OpenAI API (~600 chunks)
3. Guarda todo en PostgreSQL

### 5.2 Verificar que se Guardaron los Embeddings

Después de que termine el refresh, verifica el estado del caché:

```bash
curl -s "https://egesur.onrender.com/api/debug/cache-status"
```

**Respuesta esperada:**
```json
{
  "cache_exists": true,
  "total_chunks": 600,
  "cache_valid": true,
  "message": "Caché cargado desde PostgreSQL"
}
```

✅ **¡Listo!** Los embeddings están persistidos en PostgreSQL.

---

## Paso 6: Probar Carga Automática al Reiniciar

### 6.1 Forzar un Reinicio

Opción A: Espera 15 minutos de inactividad (Render dormirá el servicio)
Opción B: Redespliega manualmente desde el dashboard de Render

### 6.2 Verificar Logs al Despertar

Cuando el servicio se reinicie, deberías ver en los logs:

```
🚀 Iniciando servidor FastAPI...
📥 Intentando cargar caché desde PostgreSQL...
✓ Cargados 600 chunks desde PostgreSQL
✅ Caché cargado exitosamente: 600 chunks desde PostgreSQL
   Servicio listo para búsquedas instantáneas sin regenerar embeddings
```

⚡ **Tiempo total de startup: 2-5 segundos** (vs 10+ minutos sin PostgreSQL)

### 6.3 Probar una Búsqueda

```bash
curl "https://egesur.onrender.com/api/buscarNormativa?termino=seguridad"
```

Debería responder **en menos de 10 segundos** con resultados relevantes.

---

## Comandos Útiles

### Ver Chunks en la Base de Datos (Opcional)

Si instalas `psql` localmente, puedes conectarte directamente:

```bash
# Usar la External Database URL (desde el dashboard de Render)
psql postgresql://egesur_user:abc123xyz@dpg-external-abcd.oregon-postgres.render.com/egesur_db

# Ver cantidad de chunks guardados
SELECT COUNT(*) FROM document_chunks;

# Ver documentos únicos
SELECT DISTINCT source_document FROM document_chunks;

# Ver tamaño de la base de datos
SELECT pg_size_pretty(pg_database_size('egesur_db'));
```

### Limpiar la Base de Datos

Si necesitas borrar todos los embeddings:

```bash
curl -X POST "https://egesur.onrender.com/api/debug/clear-cache"
```

Luego ejecuta `refresh-cache` nuevamente para regenerar.

---

## Monitoreo y Límites

### Plan Gratuito de Render PostgreSQL

- **Almacenamiento:** 256 MB
- **Conexiones:** 97 conexiones simultáneas
- **Duración:** 90 días (luego se borra automáticamente)
- **Backups:** No incluidos en plan gratuito

### Estimación de Uso

Cada chunk ocupa aproximadamente:
- Texto: ~3000 caracteres = ~3 KB
- Embedding: 1536 floats × 8 bytes = ~12 KB
- **Total por chunk:** ~15 KB

**Para 17 PDFs (~600 chunks):**
- Uso estimado: 600 × 15 KB = **~9 MB**
- Espacio disponible: **256 MB**
- **Margen:** Puedes almacenar hasta ~4,200 chunks (~70 PDFs)

### Alertas

Si la base de datos se llena, verás este error:
```
✗ Error al guardar chunks en PostgreSQL: disk quota exceeded
```

**Solución:** Actualizar a plan de pago ($7/mes) o reducir cantidad de PDFs.

---

## Solución de Problemas

### Error: "could not connect to server"

**Causa:** DATABASE_URL incorrecta o base de datos no disponible.

**Solución:**
1. Verifica que la base de datos esté en estado "Available" en Render
2. Copia nuevamente la Internal Database URL
3. Actualiza la variable `DATABASE_URL` en Environment
4. Redespliega el servicio

### Error: "relation 'document_chunks' does not exist"

**Causa:** Las tablas no se crearon automáticamente.

**Solución:**
1. Conéctate con `psql` (ver sección "Comandos Útiles")
2. Ejecuta manualmente:
```sql
CREATE TABLE document_chunks (
    chunk_id VARCHAR PRIMARY KEY,
    text TEXT NOT NULL,
    embedding JSONB NOT NULL,
    source_document VARCHAR NOT NULL,
    source_link VARCHAR,
    chunk_index INTEGER,
    total_chunks INTEGER,
    folder_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Warning: "PostgreSQL no configurado"

**Causa:** Variable `DATABASE_URL` no está definida.

**Solución:** Sigue el Paso 3 de esta guía para agregar la variable.

---

## Upgrade a Plan de Pago (Opcional)

Si necesitas más almacenamiento o evitar el límite de 90 días:

**Render PostgreSQL - Plan Starter: $7/mes**
- 1 GB de almacenamiento
- Sin límite de tiempo
- Backups automáticos diarios
- Mayor rendimiento

Para actualizar:
1. Ve a tu base de datos en Render
2. Click en "Upgrade Plan"
3. Selecciona "Starter"

---

## Resumen del Flujo Completo

```mermaid
graph TD
    A[Servicio Duerme] --> B[Render Despierta Servicio]
    B --> C[Evento startup ejecuta]
    C --> D[Cargar chunks desde PostgreSQL]
    D --> E[Poblar CACHE en memoria]
    E --> F[Servicio listo en 2-5 seg]
    F --> G[Usuario hace búsqueda]
    G --> H[Respuesta instantánea usando CACHE]

    I[Usuario sube nuevo PDF a Drive] --> J[Usuario ejecuta /api/refresh-cache]
    J --> K[Procesar PDFs y generar embeddings]
    K --> L[Guardar en PostgreSQL + CACHE]
    L --> M[Persistido para próximos reinicios]
```

---

## Próximos Pasos

✅ **Has completado la configuración de persistencia de embeddings.**

Ahora tu API:
1. Carga embeddings desde PostgreSQL al iniciar (2-5 segundos)
2. Persiste nuevos embeddings automáticamente al ejecutar `refresh-cache`
3. No pierde datos entre reinicios del servicio

**¡Tu sistema está listo para producción!** 🎉
