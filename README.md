# Connectivity Monitor - Azure Function

Azure Function (Python v2) que monitorea conectividad DNS y TCP hacia endpoints configurados, y reporta los resultados como **Availability Tests** en Application Insights.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `function_app.py` | Código principal de la función |
| `host.json` | Configuración del runtime de Azure Functions |
| `requirements.txt` | Dependencias de Python |
| `local.settings.json.example` | Plantilla de variables de entorno |

---

## Requisitos previos de la Function App en Azure

- **Runtime:** Python 3.9, 3.10, o 3.11
- **SO:** Linux
- **Plan:** Consumption, Premium, o Dedicated
- **Application Insights:** Vinculado a la Function App
- **App Setting requerido:** `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true`

---

## Deploy (paso a paso)

### Paso 1: Descargar el código

Descargar este repositorio como ZIP: botón **Code > Download ZIP** en GitHub.

### Paso 2: Preparar el ZIP para deploy

1. Descomprimir el ZIP descargado.
2. Entrar en la carpeta del proyecto (puede llamarse `connectivity-func-main/` o similar).
3. **Re-comprimir** SOLO los archivos internos, de modo que queden en la **raíz** del ZIP:

   ```
   deploy.zip
   ├── function_app.py     ✅ en la raíz
   ├── host.json           ✅ en la raíz
   └── requirements.txt    ✅ en la raíz
   ```

   > **IMPORTANTE:** Los archivos deben estar en la raíz del ZIP, NO dentro de una subcarpeta.

### Paso 3: Deploy con Azure CLI (desde Cloud Shell)

Abrir **Azure Cloud Shell** (portal.azure.com > icono de terminal) y ejecutar:

```bash
# 1. Habilitar build remoto (instala dependencias en Azure automáticamente)
az functionapp config appsettings set \
  --resource-group <RESOURCE_GROUP> \
  --name <FUNCTION_APP_NAME> \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true

# 2. Subir el ZIP (arrastrarlo a Cloud Shell primero, o usar la ruta local)
az functionapp deployment source config-zip \
  --resource-group <RESOURCE_GROUP> \
  --name <FUNCTION_APP_NAME> \
  --src deploy.zip \
  --build-remote true
```

> **¿Por qué `--build-remote true`?**
> Azure instala las dependencias de `requirements.txt` directamente en su entorno Linux.
> Esto evita errores de módulos no encontrados causados por diferencias de plataforma (Windows vs Linux).

### Alternativa: Deploy desde Azure Portal (Kudu)

1. Ir a **Function App > Advanced Tools (Kudu) > Debug Console > CMD**.
2. Navegar a `site/wwwroot`.
3. Arrastrar y soltar los archivos (`function_app.py`, `host.json`, `requirements.txt`).
4. Ejecutar en la consola de Kudu:
   ```bash
   python -m pip install -r requirements.txt --target .python_packages/lib/site-packages
   ```

---

## Configuración de Application Settings

En **Azure Portal > Function App > Environment variables**, agregar:

| Setting | Valor | Descripción |
|---|---|---|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Runtime de la función |
| `TIMER_SCHEDULE` | `0 */5 * * * *` | Cron expression (cada 5 min en este ejemplo) |
| `RUN_LOCATION` | `East US` | Etiqueta de ubicación para los reportes en App Insights |
| `DNS_TARGETS` | `host1.com;host2.com` | Hostnames a verificar DNS, separados por `;` |
| `TCP_TARGETS` | `host1.com:443;host2.com:1433` | `host:port` a verificar TCP, separados por `;` |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | `<guid>` | Clave de instrumentación de Application Insights |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Habilita instalación de dependencias en deploy |

---

## Verificación post-deploy

1. Ir a **Function App > Functions** en Azure Portal.
2. Debe aparecer: **`connectivity_monitor`**
3. Esperar a que el timer se dispare (o hacer clic en **Test/Run** para ejecutar manualmente).
4. Revisar **Application Insights > Availability** para ver los resultados.

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'applicationinsights'` | Las dependencias no se instalaron en Azure | Verificar que `SCM_DO_BUILD_DURING_DEPLOYMENT=true` y re-deployar con `--build-remote true` |
| `0 functions found` | El archivo se llama `function.py` en vez de `function_app.py` | Renombrar a `function_app.py` |
| `WorkerConfig for runtime: python not found` | Function App configurada en Windows | Crear la Function App en **Linux** |
