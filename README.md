# Connectivity Monitor - Azure Function

Azure Function (Python v2) que monitorea conectividad DNS y TCP hacia endpoints configurados, y reporta los resultados como **Availability Tests** en Application Insights.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `function_app.py` | Código principal de la función |
| `host.json` | Configuración del runtime de Azure Functions |
| `requirements.txt` | Dependencias de Python |
| `.python_packages/` | Dependencias pre-instaladas (listas para deploy directo) |
| `local.settings.json.example` | Plantilla de variables de entorno |

---

## Requisitos de la Function App en Azure

- **Runtime:** Python 3.9, 3.10, o 3.11
- **SO:** Linux
- **Plan:** Consumption, Premium, o Dedicated
- **Application Insights:** Vinculado a la Function App

---

## Deploy desde Azure Portal (sin CLI, sin terminal)

### Paso 1: Descargar el ZIP desde GitHub

En este repositorio, hacer clic en **Code > Download ZIP** y guardar el archivo.

### Paso 2: Preparar el ZIP para deploy

El ZIP de GitHub mete todo dentro de una subcarpeta (ej: `connectivity-func-main/`).
Azure necesita los archivos en la **raíz** del ZIP.

1. **Descomprimir** el ZIP descargado.
2. **Entrar** en la carpeta interna (ej: `connectivity-func-main/`).
3. **Seleccionar todo** el contenido de adentro (Ctrl+A).
4. **Clic derecho > Comprimir en archivo ZIP** (o "Send to > Compressed folder" en Windows).
5. Nombrar el nuevo ZIP: `deploy.zip`.

La estructura correcta debe ser:

```
deploy.zip
├── function_app.py          ✅ directamente en la raíz
├── host.json                ✅ directamente en la raíz
├── requirements.txt         ✅ directamente en la raíz
└── .python_packages/        ✅ directamente en la raíz
    └── lib/site-packages/
        ├── applicationinsights/
        ├── azure/functions/
        └── ...
```

> **IMPORTANTE:** Si los archivos quedan DENTRO de una subcarpeta en el ZIP, el deploy fallará.

### Paso 3: Subir a Azure Portal

1. Ir a **Azure Portal** → tu **Function App**.
2. En el menú izquierdo, hacer clic en **Advanced Tools**.
3. Hacer clic en **Go →** (se abre Kudu en una nueva pestaña).
4. En Kudu, ir a **Tools → Zip Push Deploy**.
5. **Arrastrar y soltar** tu `deploy.zip` en la zona de upload.
6. Esperar a que termine el deploy.

### Paso 4: Verificar

1. Volver a **Azure Portal → Function App → Functions**.
2. Debe aparecer: **`connectivity_monitor`** ✅
3. Hacer clic en la función → **Test/Run** para probarla manualmente.

---

## Configuración de Application Settings

En **Azure Portal → Function App → Environment variables**, agregar estas variables y hacer clic en **Apply**:

| Setting | Valor | Descripción |
|---|---|---|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Runtime de la función |
| `TIMER_SCHEDULE` | `0 */5 * * * *` | Cron expression (cada 5 minutos) |
| `RUN_LOCATION` | `East US` | Etiqueta de ubicación para App Insights |
| `DNS_TARGETS` | `host1.com;host2.com` | Hostnames DNS a verificar, separados por `;` |
| `TCP_TARGETS` | `host1.com:443;host2.com:1433` | `host:port` TCP a verificar, separados por `;` |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | `<guid>` | Clave de instrumentación de Application Insights |

---

## Verificación post-deploy

1. Ir a **Function App → Functions**.
2. Debe aparecer: **`connectivity_monitor`**
3. Esperar a que el timer se dispare, o ejecutar manualmente con **Test/Run**.
4. Revisar **Application Insights → Availability** para ver los resultados.

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'applicationinsights'` | `.python_packages/` no está en el ZIP o no está en la raíz | Re-crear el ZIP verificando que `.python_packages/` esté en la raíz |
| `0 functions found` | El archivo no se llama `function_app.py` | Verificar que el archivo se llama exactamente `function_app.py` |
| `WorkerConfig for runtime: python not found` | Function App creada en Windows | Recrear la Function App seleccionando **Linux** como SO |
| La función no aparece | El ZIP tiene subcarpeta en la raíz | Abrir el ZIP y verificar que `function_app.py` esté directamente en la raíz |
