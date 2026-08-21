# Connectivity Monitor - Azure Function

Azure Function (Python v2) que monitorea conectividad DNS y TCP hacia endpoints configurados y publica telemetría en Application Insights mediante OpenTelemetry.

Cada chequeo genera:

- Un span en la tabla `dependencies`, con estado, duración, destino, ubicación y mensaje.
- Las métricas `connectivity.check.count` y `connectivity.check.duration` en `customMetrics`.

OpenTelemetry no escribe en `availabilityResults`; la vista **Availability** se reemplaza por consultas, alertas o workbooks basados en `dependencies` y `customMetrics`.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `function_app.py` | Código principal de la función |
| `host.json` | Configuración del runtime de Azure Functions |
| `requirements.txt` | Dependencias de Python |
| `local.settings.json.example` | Plantilla de variables de entorno |
| `test_function_app.py` | Prueba unitaria de la instrumentación OpenTelemetry |

---

## Requisitos de la Function App en Azure

- **Azure Functions runtime:** 4.x
- **Python:** 3.13
- **SO:** Linux
- **Plan:** Flex Consumption (recomendado), Consumption, Premium, o Dedicated
- **Application Insights:** Vinculado a la Function App
- **Storage Account:** Debe tener Managed Identity configurada (si key access está deshabilitado)

---

## Desarrollo local

Crear un entorno con la misma versión de Python usada en Azure:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item local.settings.json.example local.settings.json
func start
```

Completar `local.settings.json` antes de ejecutar la función. Este archivo contiene secretos y no se versiona.

---

## Deploy

Usar build remoto para que Azure instale las dependencias nativas para Linux. Las opciones recomendadas son:

- VS Code: **Azure Functions: Deploy to Function App**.
- Azure Functions Core Tools:

```powershell
func azure functionapp publish <FUNCTION_APP_NAME> --python
```

No incluir `.venv` ni `.python_packages` creados en Windows. `azure-monitor-opentelemetry` contiene dependencias nativas y deben compilarse o descargarse para Linux durante el build remoto.

## Configuración de Application Settings

En **Azure Portal → Function App → Environment variables**, agregar estas variables y hacer clic en **Apply**:

| Setting | Valor | Descripción |
|---|---|---|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Runtime de la función |
| `TIMER_SCHEDULE` | `0 * 0,12-23 * * *` | Cron expression en UTC para Flex Consumption (cada minuto entre 7:00 y 19:59 hora Colombia) |
| `RUN_LOCATION` | `East US` | Etiqueta de ubicación para App Insights |
| `DNS_TARGETS` | `host1.com;host2.com` | Hostnames DNS a verificar, separados por `;` |
| `TCP_TARGETS` | `host1.com:443;host2.com:1433` | `host:port` TCP a verificar, separados por `;` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `<connection-string>` | Connection string del recurso de Application Insights |
| `PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY` | `true` | Habilita OpenTelemetry en el worker Python |
| `OTEL_TRACES_SAMPLER` | `always_on` | Conserva todos los spans de conectividad |
| `OTEL_SERVICE_NAME` | `connectivity-monitor` | Cloud role name mostrado en Application Insights |

---

## Verificación post-deploy

1. Ir a **Function App → Functions**.
2. Debe aparecer: **`connectivity_monitor`**
3. Esperar a que el timer se dispare, o ejecutar manualmente con **Test/Run**.
4. Ir a **Application Insights → Logs** y ejecutar:

```kusto
dependencies
| where name startswith "DNS::" or name startswith "TCP::"
| extend
    checkType = tostring(customDimensions["connectivity.check.type"]),
    target = tostring(customDimensions["connectivity.target"]),
    runLocation = tostring(customDimensions["connectivity.run.location"]),
    durationMs = toint(customDimensions["connectivity.duration_ms"]),
    message = tostring(customDimensions["connectivity.message"])
| project timestamp, name, success, durationMs, checkType, target, runLocation, message
| order by timestamp desc
```

Para consultar las métricas:

```kusto
customMetrics
| where name in ("connectivity.check.count", "connectivity.check.duration")
| project timestamp, name, value, customDimensions
| order by timestamp desc
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

---

## Troubleshooting

| Error | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'azure.monitor'` | Dependencias no instaladas o deploy sin build remoto | Instalar `requirements.txt` localmente y volver a publicar con build remoto |
| No aparece telemetría | Falta la connection string o el worker OTel no está habilitado | Verificar `APPLICATIONINSIGHTS_CONNECTION_STRING`, `PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY` y `telemetryMode` |
| No aparece `connectivity_monitor` en Functions | Los archivos están dentro de una subcarpeta en el ZIP | Descomprimir, entrar a la subcarpeta, y re-comprimir desde ahí |
| Error 401/403 al entrar a Kudu | No tiene permisos | Verificar que el usuario tenga rol Contributor o superior en la Function App |
| `0 functions found` | El archivo no se llama `function_app.py` | Verificar que el archivo se llama exactamente `function_app.py` |
| `WorkerConfig for runtime: python not found` | Function App creada en Windows | Recrear la Function App seleccionando **Linux** como SO |
