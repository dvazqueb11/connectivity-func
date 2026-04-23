# Connectivity Monitor - Azure Function

Azure Function (Python v2) que monitorea conectividad DNS y TCP hacia endpoints configurados, y reporta los resultados como **Availability Tests** en Application Insights.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `function_app.py` | Código principal de la función |
| `host.json` | Configuración del runtime de Azure Functions |
| `requirements.txt` | Dependencias de Python (Azure las instala automáticamente) |
| `local.settings.json.example` | Plantilla de variables de entorno |

---

## Requisitos de la Function App en Azure

- **Runtime:** Python 3.9, 3.10, o 3.11
- **SO:** Linux
- **Plan:** Consumption, Premium, o Dedicated
- **Application Insights:** Vinculado a la Function App

---

## Deploy desde Azure Portal (sin CLI, sin terminal)

### Paso 1: Configurar Application Settings

Antes de conectar el repo, agrega esta variable en **Environment variables** (ver sección más abajo):

| Setting | Valor |
|---|---|
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `1` |

Esto hace que Azure instale automáticamente las dependencias de `requirements.txt` al desplegar.

### Paso 2: Conectar GitHub en Deployment Center

1. Ir a **Azure Portal** → tu **Function App**.
2. En el menú izquierdo, hacer clic en **Deployment Center**.
3. En **Source**, seleccionar **GitHub**.
4. Si es la primera vez, hacer clic en **Authorize** para vincular tu cuenta de GitHub.
5. Seleccionar:
   - **Organization:** `dvazqueb11` (o la org correspondiente)
   - **Repository:** `connectivity-func`
   - **Branch:** `main`
6. Hacer clic en **Save**.

Azure automáticamente:
- Descarga el código del repositorio
- Instala las dependencias de `requirements.txt`
- Despliega la función

### Paso 3: Verificar

1. En Deployment Center, esperar a que el estado del deploy sea ✅ **Success**.
2. Ir a **Function App → Functions**.
3. Debe aparecer: **`connectivity_monitor`** ✅
4. Hacer clic en la función → **Test/Run** para probarla manualmente.

> **Para re-desplegar:** Cada vez que se haga `git push` al branch `main`, Azure despliega automáticamente.

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
