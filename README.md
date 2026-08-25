# Crop Guardian uAI

Multi-agent system that diagnoses crop diseases from a photograph.

A user uploads a photo from the browser. A local vision model identifies the
crop, the image is routed to the diagnosis agent specialised in that crop, a
second agronomist agent writes the treatment, and the result is stored as
history in Azure Cosmos DB.

<!-- TODO: captura o GIF de la app aqui -->

## Architecture

**Frontend** — React 19 + TypeScript + Vite. `src/App.tsx` holds the state and
distributes it to the components in `src/components/`. All backend calls go
through `src/services/api.ts`.

An analysis chains two agent calls and can take up to a minute, so while it
runs `UploadForm` disables its inputs and draws an ink sprout next to the
status line. Failures land in the same slot as the form's own validation
errors. The animation stops under `prefers-reduced-motion`, leaving the sprout
drawn.

**Backend** — Flask API in `src/backend/`. `app.py` exposes the routes and is
the only module that talks to Cosmos DB. Each agent lives in its own file:

| Module | Role |
| --- | --- |
| `crop_router.py` | Classifies the crop with a local multimodal model (LM Studio) and decides which agent to route to. |
| `diagnostico_agent.py` | Sends the image to the Azure AI Foundry diagnosis agent. |
| `tratamiento_agent.py` | Sends the diagnosis to the agronomist agent. |
| `seguimiento_agent.py` | Compares current severity against history and classifies the trend. No cloud calls. |

Classifying before calling the cloud avoids spending tokens and allows agents
whose instructions are scoped to a single crop:

| Detected crop | Agent |
| --- | --- |
| Tomatoes | `AZURE_AI_AGENT3_NAME` |
| Grapes | `AZURE_AI_AGENT4_NAME` |
| Cherries | `AZURE_AI_AGENT5_NAME` |
| No clear match | `AZURE_AI_AGENT1_NAME` (general) |

If LM Studio is unavailable the router degrades to the general agent instead
of failing.

## Flow

```
POST /api/analizar-cultivo  { imagen (base64), nombre_planta }
  → clasificar_cultivo()       LM Studio  → Tomates | Uvas | Cerezas | General
  → diagnostico()              Foundry    → enfermedad, severidad, síntomas, confianza
  → recomendar_tratamiento()   Foundry    → explicación, tratamiento, prevención, urgencia
  → proxima_revision = now (UTC) + proxima_revision_dias
  → writes the document to Cosmos DB
  → returns the combined JSON
```

If the Cosmos write fails the error is logged but the response is still
delivered.

## Evaluation

The diagnosis chain was measured against a labelled golden set of 40 images
spanning 10 crops and 12 diseases (PlantVillage). The harness lives in
`src/backend/test_golden_set*.py`; raw model outputs are committed in
`resultados_golden_set*.json`.

| Metric | Result |
| --- | --- |
| Crop routing | 15/40 (37.5%) |
| Disease diagnosis | 13/40 (32.5%) |

Per crop:

| Crop | n | Routing | Diagnosis |
| --- | --- | --- | --- |
| Cherries | 10 | 1/10 | 8/10 |
| Tomatoes | 10 | 7/10 | 3/10 |
| Grapes | 10 | 7/10 | 0/10 |

Disease matching is loose. A case counts as correct if any ES/EN synonym
from `KEYWORDS_ENFERMEDAD` turns up as a substring in the agent's
`enfermedad`, `razonamiento` or `sintomas`, accents stripped. All 12 diseases
have keyword entries, so the low scores are not a string-comparison artifact.

Some notes on the numbers.

The aggregate is unfair to the router. The set covers 10 crops and the router
handles 3, so the other 7 can only ever score as `General`. Over supported
crops alone, routing is 15/30.

Specialisation did not pay off. Cherries were routed wrong 9 times out of 10
and still gave the best diagnosis of the three, 8/10. The general agent beat
the specialised ones.

Grapes at 0/10 is a configuration problem rather than a reading problem. The
grape agent answers Excoriosis, Oídio and Septoria; the dataset labels Black
Rot, Esca and Leaf Blight. The two vocabularies do not overlap, so the agent
cannot score above zero however well it reads the image.

Mean confidence reported by the agents was 0.67.

The images are not in the repository. The harness expects them under
`src/backend/golden_set_3/`.

## Requirements

Node.js 20+, Python 3.10+, Azure CLI, an Azure AI Foundry account with the
agents published, and a Cosmos DB account (NoSQL API) with database
`cultivos_db`, container `diagnosticos` and partition key `/agricultor_id`.

Optionally, LM Studio with a vision model loaded and its local server
running. Without it, every photo goes to the general agent.

## Configuration

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI Foundry project endpoint |
| `AZURE_AI_AGENT1_NAME` | General diagnosis agent (fallback) |
| `AZURE_AI_AGENT2_NAME` | Agronomist treatment agent |
| `AZURE_AI_AGENT3_NAME` | Tomato diagnosis |
| `AZURE_AI_AGENT4_NAME` | Grape diagnosis |
| `AZURE_AI_AGENT5_NAME` | Cherry diagnosis |
| `COSMOS_URI` | Cosmos DB account URI |
| `COSMOS_KEY` | Cosmos DB master key |
| `LMSTUDIO_BASE_URL` | LM Studio endpoint. Defaults to `http://127.0.0.1:1234/v1`; from a container this must point at the host. |
| `ENTORNO` | `local` enables the development identity below. Anything else (including unset) requires the platform identity header. |
| `DEV_AGRICULTOR_ID` | Identity used for local development. Only honoured when `ENTORNO=local`. |

`.env` is excluded from version control. Foundry authentication uses
`DefaultAzureCredential`, i.e. your Azure CLI session (`az login`), separate
from the Cosmos key.

## Authentication

The hosting platform handles the login and injects a verified identity
header, `X-MS-CLIENT-PRINCIPAL-ID`. `resolver_agricultor()` in `app.py` reads
it on every `/api/` route and answers `401` without it.

Cosmos queries are scoped to that identity's partition, so one farmer cannot
read or delete another's documents. `agricultor_id` never comes from the
request body.

For local development, set `ENTORNO=local` and `DEV_AGRICULTOR_ID`. The
default is production, so a forgotten variable shows up as `401` instead of
quietly disabling authentication.

> The container must not be reachable except through that authentication
> layer, or the header can just be sent by hand.

Error messages from the API are shown to the user only for `4xx` responses,
which are actionable (missing photo, image too large, expired session). A
`5xx` returns `str(e)`, so the UI shows a generic message and the detail stays
in the server log.

## Running

### Local development

Backend:

```bash
cd src/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # http://localhost:5000
```

Frontend, from the repository root:

```bash
npm install
npm run dev                        # http://localhost:5173
```

The Vite dev server proxies `/api` to `localhost:5000` (see
`vite.config.ts`), so the frontend uses same-origin relative URLs in both
development and production.

Other scripts: `npm run build` (types + build), `npm run preview`,
`npm run lint`.

### Container

The root `Dockerfile` builds in two stages: Node compiles the frontend, then
`dist/` is copied into the Flask image as `static/`. One container serves the
UI and the API from the same origin.

```bash
docker build -t crop-guardian .
docker run --rm -p 5000:5000 \
  --add-host=host.docker.internal:host-gateway \
  --env-file .env \
  crop-guardian
```

`--add-host` plus `LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1`
lets the container reach LM Studio on the host. Without it every photo goes to
the general agent.

In production, pass the variables through the platform's configuration rather
than `--env-file`, and leave `ENTORNO` unset.

## API

| Route | Description |
| --- | --- |
| `GET /api/health` | Liveness probe. Public, touches neither Cosmos nor the agents. |
| `POST /api/analizar-cultivo` | Analyses a photo and records the result. Body: `imagen` (base64) and `nombre_planta`. `400` if either is missing, `413` above 10 MB. |
| `GET /api/historial` | Every document for the authenticated farmer, newest first. |
| `GET /api/plantas` | One row per plant with its most recent document and a `vencido` flag once the review date has passed. |
| `DELETE /api/plantas/<nombre_planta>` | Deletes that plant's whole history. Returns `{"eliminados": n}` or `404`. |

Response of `POST /api/analizar-cultivo`:

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
  "proxima_revision": "2026-08-21T10:32:11.482913+00:00"
}
```

Each analysis writes a document to `diagnosticos` with `id`, `agricultor_id`,
`nombre_planta`, `cultivo_detectado`, `fecha`, `proxima_revision`, `resultado`
and `tratamiento`. Timestamps are timezone-aware UTC. Response types live in
`src/types/diagnostico.ts`.

## Tests

```bash
pip install -r src/backend/requirements-dev.txt
pytest
```

The suite runs offline. `src/backend/tests/conftest.py` installs doubles for
Cosmos and the Foundry agents before importing `app`, so it needs no Azure
credentials, no network and no `.env`. The Cosmos double asserts that every
query carries a `partition_key`, so an unscoped query breaks the suite instead
of leaking documents between farmers.

Covered: authentication and the `ENTORNO` rule, isolation between farmers on
read and delete, timezones including the old naive timestamps, and the upload
size limit.

`scripts/comprobar_agente.py` is a manual check against a live Foundry agent.
It is not part of the suite and does need credentials.

## Limitations

- **`AgenteSeguimiento` is not wired in.** The class exists and the frontend
  has its component (`EvolutionCard.tsx`), but `app.py` does not call it yet.
  Its `ORDEN_SEVERIDAD` also expects `sano`/`leve`/`moderado`/`severo`, while
  the agents answer `Leve`, `Media`, `Alta`, `Crítica` and `Desconocida`, so
  every comparison would fall back to the default and report `sin_cambios`.
  Both need fixing before it is connected.
- **Agent output is unvalidated.** The modules return the model's text as-is
  and the caller runs `json.loads()`; a malformed response becomes a `500`.
- **Per-crop routing needs LM Studio reachable.** Where it is not, every
  photo falls back to the general agent without saying so. Going by the
  evaluation, that is not clearly worse.
- **Logging is `print`.** Works in a container with `PYTHONUNBUFFERED=1`, but
  there is no severity, no filtering, and full agent responses get echoed.
- **Dependencies are unpinned.** `azure-ai-projects` is a preview SDK and its
  agent-invocation surface has changed between releases.
- **Datasets and `.pt` weights live outside the repository**, excluded by
  `.gitignore` because of their size.
