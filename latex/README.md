# Documento de Transferencia Técnica (LaTeX)

## Compilación del PDF

Para compilar el documento LaTeX a PDF:

### Opción 1: Usando pdflatex (Local)

```bash
# Compilar el documento (ejecutar 2 veces para generar tabla de contenidos)
cd latex
pdflatex transferencia_tecnica.tex
pdflatex transferencia_tecnica.tex

# El PDF se generará como: transferencia_tecnica.pdf
```

### Opción 2: Usando Overleaf (Online)

1. Ir a [https://www.overleaf.com](https://www.overleaf.com)
2. Crear nuevo proyecto → Upload Project
3. Subir `transferencia_tecnica.tex`
4. Click en "Recompile"
5. Descargar PDF generado

### Opción 3: Usando MiKTeX (Windows)

1. Descargar e instalar MiKTeX: [https://miktex.org/download](https://miktex.org/download)
2. Abrir MiKTeX Console → Instalar paquetes faltantes si es necesario
3. Ejecutar desde línea de comandos:
```bash
pdflatex transferencia_tecnica.tex
```

### Opción 4: Usando TeX Live (Linux/Mac)

```bash
# Linux
sudo apt-get install texlive-full

# Mac
brew install --cask mactex

# Compilar
pdflatex transferencia_tecnica.tex
```

## Contenido del Documento

El documento de transferencia técnica incluye:

1. **Resumen Ejecutivo** - Propósito y tecnologías
2. **Arquitectura del Sistema** - Componentes y flujo de datos
3. **Configuración y Despliegue** - Variables de entorno y pasos de deployment
4. **Operación y Mantenimiento** - Endpoints, tareas de mantenimiento, rotación de credenciales
5. **Solución de Problemas** - Troubleshooting común
6. **Estructura del Repositorio** - Organización de archivos

**Total:** ~8-10 páginas

## Notas

- El documento está optimizado para impresión en tamaño A4
- Utiliza colores para resaltar código y diagramas
- Incluye tablas de referencia rápida
- Diseñado para equipo de TI sin conocimiento previo del sistema
