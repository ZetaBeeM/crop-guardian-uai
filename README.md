# Crop Guardian uAI

Sistema multiagente para el diagnóstico de enfermedades en cultivos a partir de una fotografía.

El usuario sube una foto desde el navegador. Un clasificador local identifica el cultivo, la imagen se envía al agente de diagnóstico especializado en ese cultivo, un segundo agente agrónomo redacta el tratamiento y el resultado se almacena como historial en Azure Cosmos DB.

## Arquitectura

**Frontend**: React 19 + TypeScript + Vite. `src/App.tsx` concentra el estado y lo reparte entre los componentes de `src/components/`. Las llamadas al backend pasan por `src/services/api.ts`.

**Backend**: API Flask en `src/backend/`. `app.py` expone las rutas y es el único módulo que habla con Cosmos DB. Cada agente vive en su propio archivo:

`crop_router.py` - Clasifica el cultivo con un modelo multimodal local (LM Studio) y decide a qué agente enrutar. |
`diagnostico_agent.py` - Envía la imagen al agente de diagnóstico apropiado para el cultivo de Azure AI Foundry.
`tratamiento_agent.py` - Envía el diagnóstico al agente agrónomo.
`seguimiento_agent.py` - Compara la severidad actual contra el historial y clasifica la tendencia.

Clasificar antes de llamar a la nube evita gastar tokens y permite agentes con instrucciones acotadas a un cultivo:

Tomates se envian a `AZURE_AI_AGENT3_NAME`, uvas a `AZURE_AI_AGENT4_NAME`, cerezas a `AZURE_AI_AGENT5_NAME`, y si el cultivo no coincide con estos, `AZURE_AI_AGENT1_NAME` (general)

Si LM Studio no está disponible, el enrutador manda automaticamente las imagenes al agente general en lugar de fallar.

## Flujo

```
POST /analizar-cultivo  { imagen (base64), nombre_planta }
  → clasificar_cultivo()       LM Studio  → Tomates | Uvas | Cerezas | General
  → diagnostico()              Foundry    → enfermedad, severidad, síntomas, confianza
  → recomendar_tratamiento()   Foundry    → explicación, tratamiento, prevención, urgencia
  → proxima_revision = ahora + proxima_revision_dias
  → guarda el documento en Cosmos DB
  → responde el JSON combinado
```

Si la escritura en Cosmos falla, el error se registra pero la respuesta se entrega igual.

## Requisitos

Node.js 20+, Python 3.10+, Azure CLI, una cuenta de Azure AI Foundry con los agentes publicados y una de Cosmos DB (API NoSQL) con la base `cultivos_db`, el contenedor `diagnosticos` y clave de partición `/agricultor_id`.

Opcionalmente, LM Studio con un modelo de visión cargado y el servidor local activo. Sin él, todas las fotos van al agente general.

## Configuración

```bash
cp .env.example .env
```

| Variable | Descripción |
| --- | --- |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Endpoint del proyecto de Azure AI Foundry |
| `AZURE_AI_AGENT1_NAME` | Agente de diagnóstico general (fallback) |
| `AZURE_AI_AGENT2_NAME` | Agente agrónomo de tratamiento |
| `AZURE_AI_AGENT3_NAME` | Diagnóstico de tomates |
| `AZURE_AI_AGENT4_NAME` | Diagnóstico de uvas |
| `AZURE_AI_AGENT5_NAME` | Diagnóstico de cerezas |
| `COSMOS_URI` | URI de la cuenta de Cosmos DB |
| `COSMOS_KEY` | Clave maestra de Cosmos DB |

La autenticación contra Foundry usa `DefaultAzureCredential`, es decir tu sesión de Azure CLI (`az login`), independiente de la clave de Cosmos.

## Setup

Backend:

```bash
cd src/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # http://localhost:5000
```

Frontend, desde la raíz:

```bash
npm install
npm run dev                        # http://localhost:5173
```

Para probar el clasificador de forma aislada: `python src/backend/classify_crop.py imagen.jpg`.

## API

Base: `http://localhost:5000`

| Ruta | Descripción |
| --- | --- |
| `POST /analizar-cultivo` | Analiza una foto y registra el resultado. Cuerpo: `imagen` (base64), `nombre_planta` y, opcionalmente, `agricultor_id` (por defecto `agricultor-demo`). Devuelve `400` si falta la imagen o el nombre. |
| `GET /historial` | Todos los documentos, del más reciente al más antiguo. |
| `GET /plantas` | Una fila por planta con su documento más reciente y un campo `vencido` si ya pasó la fecha de revisión. |
| `DELETE /plantas/<nombre_planta>` | Elimina todo el historial de esa planta. Responde `{"eliminados": n}` o `404`. |

Ejemplo de respuesta de `POST /analizar-cultivo`:

```json
{
  "diagnostico": {
    "planta": "Tomate",
    "enfermedad": "Tizón tardío",
    "severidad": "moderado",
    "sintomas": ["manchas necróticas en hojas"],
    "confianza": 0.87,
    "razonamiento": "...",
    "urgente": false
  },
  "tratamiento": {
    "explicacion": "...",
    "tratamiento": "...",
    "prevencion": "...",
    "urgencia": "media",
    "proxima_revision_dias": 7
  },
  "nombre_planta": "Tomatera del invernadero",
  "cultivo_detectado": "Tomates",
  "proxima_revision": "2026-08-21T10:32:11.482913"
}
```

Cada análisis genera un documento en `diagnosticos` con `id`, `agricultor_id`, `nombre_planta`, `cultivo_detectado`, `fecha`, `proxima_revision`, `resultado` y `tratamiento`. Los tipos de las respuestas están en `src/types/diagnostico.ts`.
