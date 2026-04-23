# Connectivity Monitor - Azure Function

Azure Function (Python v2) que monitorea conectividad DNS y TCP hacia endpoints configurados, y reporta los resultados como **Availability Tests** en Application Insights.

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `function_app.py` | Código principal de la función |
| `host.json` | Configuración del runtime de Azure Functions |
| `requirements.txt` | Dependencias de Python |
| `.python_packages/` | Dependencias pre-instaladas (necesarias para ZIP deploy) |
| `local.settings.json.example` | Plantilla de variables de entorno |

---

## Deploy (ZIP directo en Azure Portal o CLI)

### Opción A: Deploy desde Azure Portal (más sencillo)

1. **Descargar** este repositorio como ZIP (botón **Code > Download ZIP** en GitHub).
2. Descomprimir el ZIP descargado.
3. **Re-comprimir** solo el contenido de la carpeta `connectivity-func/` asegurándote de que los archivos queden en la **raíz del ZIP** (NO dentro de una subcarpeta):
   ```
   mi-deploy.zip
   ├── function_app.py        ✅ en la raíz
   ├── host.json              ✅ en la raíz
   ├── requirements.txt       ✅ en la raíz
   └── .python_packages/      ✅ en la raíz
   ```
4. En **Azure Portal** ir a tu Function App > **Advanced Tools (Kudu)** > **Tools > Zip Push Deploy**.
5. Arrastrar el ZIP.

### Opción B: Deploy con Azure CLI

```bash
# Desde Cloud Shell o terminal con Azure CLI
az functionapp deployment source config-zip \
  --resource-group <RESOURCE_GROUP> \
  --name <FUNCTION_APP_NAME> \
  --src <ruta-al-zip> \
  --build-remote true
```

> **Nota:** Si usas `--build-remote true`, Azure instalará las dependencias automáticamente y no necesitas la carpeta `.python_packages/`.

---

## Configuración de Application Settings

En **Azure Portal > Function App > Configuration > Application Settings**, agregar:

| Setting | Valor | Descripción |
|---|---|---|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Runtime de la función |
| `TIMER_SCHEDULE` | `0 */5 * * * *` | Cron (cada 5 min en este ejemplo) |
| `RUN_LOCATION` | `East US` | Etiqueta de ubicación para App Insights |
| `DNS_TARGETS` | `host1.com;host2.com` | Hostnames a verificar DNS, separados por `;` |
| `TCP_TARGETS` | `host1.com:443;host2.com:1433` | `host:port` a verificar TCP, separados por `;` |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | `<guid>` | Clave de instrumentación de App Insights |

---

## Verificación post-deploy

1. Ir a **Function App > Functions** en Azure Portal.
2. Debe aparecer: **`connectivity_monitor`**
3. Esperar a que el timer se dispare (o ejecutar manualmente desde el portal).
4. Revisar **Application Insights > Availability** para ver los resultados.

---

## Requisitos de la Function App en Azure

- **Runtime:** Python 3.9, 3.10, o 3.11
- **Plan:** Consumption, Premium, o Dedicated
- **Application Insights:** Vinculado a la Function App
