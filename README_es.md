# Crop Guardian uAI

Sistema multiagente para el diagnóstico de enfermedades en cultivos a partir de una fotografía.

El usuario sube una foto desde el navegador. Un clasificador local identifica el cultivo, la imagen se envía al agente de diagnóstico especializado en ese cultivo, un segundo agente agrónomo redacta el tratamiento y el resultado se almacena como historial en Azure Cosmos DB.

## Arquitectura

**Frontend** — React 19 + TypeScript + Vite. `src/App.tsx` concentra el estado y lo reparte entre los componentes de `src/components/`. Las llamadas al backend pasan por `src/services/api.ts`.

Un análisis encadena dos llamadas a los agentes y puede tardar hasta un minuto, así que mientras corre `UploadForm` deshabilita sus campos y dibuja un brote a tinta junto al aviso. Los fallos aparecen en el mismo hueco que los errores de validación del propio formulario. La animación se detiene con `prefers-reduced-motion` y el brote queda dibujado.

Los mensajes de error de la API solo se muestran tal cual en las respuestas `4xx`, que son accionables (falta la foto, imagen muy grande, sesión caducada). Un `5xx` devuelve `str(e)`, así que la interfaz muestra un mensaje genérico y el detalle se queda en el log.

**Backend** — API Flask en `src/backend/`. `app.py` expone las rutas y es el único módulo que habla con Cosmos DB. Cada agente vive en su propio archivo:

| Módulo | Rol |
| --- | --- |
| `crop_router.py` | Clasifica el cultivo con un modelo multimodal local (LM Studio) y decide a qué agente enrutar. |
| `diagnostico_agent.py` | Envía la imagen al agente de diagnóstico de Azure AI Foundry. |
| `tratamiento_agent.py` | Envía el diagnóstico al agente agrónomo. |
| `seguimiento_agent.py` | Compara la severidad actual contra el historial y clasifica la tendencia. Sin llamadas a la nube. |

Clasificar antes de llamar a la nube evita gastar tokens y permite agentes con instrucciones acotadas a un cultivo:

| Cultivo detectado | Agente |
| --- | --- |
| Tomates | `AZURE_AI_AGENT3_NAME` |
| Uvas | `AZURE_AI_AGENT4_NAME` |
| Cerezas | `AZURE_AI_AGENT5_NAME` |
| Sin coincidencia clara | `AZURE_AI_AGENT1_NAME` (general) |

Si LM Studio no está disponible, el enrutador degrada al agente general en lugar de fallar.

## Flujo

```
POST /api/analizar-cultivo  { imagen (base64), nombre_planta }
  → clasificar_cultivo()       LM Studio  → Tomates | Uvas | Cerezas | General
  → diagnostico()              Foundry    → enfermedad, severidad, síntomas, confianza
  → recomendar_tratamiento()   Foundry    → explicación, tratamiento, prevención, urgencia
  → proxima_revision = ahora (UTC) + proxima_revision_dias
  → guarda el documento en Cosmos DB
  → responde el JSON combinado
```

Si la escritura en Cosmos falla, el error se registra pero la respuesta se entrega igual.

## Evaluación

La cadena de diagnóstico se midió contra un golden set etiquetado de 40
imágenes, 10 cultivos y 12 enfermedades (PlantVillage). El arnés está en
`src/backend/test_golden_set*.py` y las salidas crudas del modelo en
`resultados_golden_set*.json`.

| Métrica | Resultado |
| --- | --- |
| Enrutamiento de cultivo | 15/40 (37,5%) |
| Diagnóstico de enfermedad | 13/40 (32,5%) |

Por cultivo:

| Cultivo | n | Enrutamiento | Diagnóstico |
| --- | --- | --- | --- |
| Cerezas | 10 | 1/10 | 8/10 |
| Tomates | 10 | 7/10 | 3/10 |
| Uvas | 10 | 7/10 | 0/10 |

El emparejamiento de enfermedades es laxo: cuenta como acierto si algún
sinónimo ES/EN de `KEYWORDS_ENFERMEDAD` aparece como substring en
`enfermedad`, `razonamiento` o `sintomas`, sin acentos. Las 12 enfermedades
tienen entrada, así que las cifras bajas no vienen de comparar cadenas de
forma estricta.

Algunas notas sobre los números.

El agregado es injusto con el router. El set cubre 10 cultivos y el router
maneja 3, así que los otros 7 solo pueden puntuar como `General`. Sobre
cultivos soportados el enrutamiento es 15/30.

Especializar no rindió. Cerezas se enrutó mal 9 de cada 10 veces y aun así dio
el mejor diagnóstico de los tres, 8/10. El agente general le ganó a los
especializados.

El 0/10 en uvas es un problema de configuración, no de lectura de la imagen.
El agente de uvas responde Excoriosis, Oídio y Septoria; el dataset etiqueta
Black Rot, Esca y Leaf Blight. Los dos vocabularios no se solapan, así que el
agente no puede puntuar por encima de cero.

La confianza media declarada por los agentes fue 0,67.

Las imágenes no están en el repositorio. El arnés las espera en
`src/backend/golden_set_3/`.

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
| `LMSTUDIO_BASE_URL` | Endpoint de LM Studio. Por defecto `http://127.0.0.1:1234/v1`; desde un contenedor debe apuntar al host. |
| `ENTORNO` | `local` habilita la identidad de desarrollo. Cualquier otro valor (o sin definir) exige la cabecera de identidad de la plataforma. |
| `DEV_AGRICULTOR_ID` | Identidad para desarrollo local. Solo se respeta si `ENTORNO=local`. |

`.env` está excluido del control de versiones. La autenticación contra Foundry usa `DefaultAzureCredential`, es decir tu sesión de Azure CLI (`az login`), independiente de la clave de Cosmos.

## Puesta en marcha

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

Otros scripts: `npm run build` (tipos + compilación), `npm run preview`, `npm run lint`.

Para probar el clasificador de forma aislada: `python src/backend/classify_crop.py imagen.jpg`.

## API

Base: `http://localhost:5000`

| Ruta | Descripción |
| --- | --- |
| `GET /api/health` | Sonda de vida. Pública; no toca Cosmos ni los agentes. |
| `POST /api/analizar-cultivo` | Analiza una foto y registra el resultado. Cuerpo: `imagen` (base64) y `nombre_planta`. Devuelve `400` si falta alguno, `413` si supera 10 MB. |
| `GET /api/historial` | Todos los documentos del agricultor autenticado, del más reciente al más antiguo. |
| `GET /api/plantas` | Una fila por planta con su documento más reciente y un campo `vencido` si ya pasó la fecha de revisión. |
| `DELETE /api/plantas/<nombre_planta>` | Elimina todo el historial de esa planta. Responde `{"eliminados": n}` o `404`. |

La plataforma de hosting valida el login e inyecta la cabecera
`X-MS-CLIENT-PRINCIPAL-ID`. `resolver_agricultor()` en `app.py` la lee en cada
ruta `/api/` y responde `401` sin ella. Las consultas a Cosmos se limitan a la
partición de esa identidad y el `agricultor_id` nunca sale del cuerpo de la
petición. Para desarrollo local: `ENTORNO=local` y `DEV_AGRICULTOR_ID`.

Respuesta de `POST /analizar-cultivo`:

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

Cada análisis genera un documento en `diagnosticos` con `id`, `agricultor_id`, `nombre_planta`, `cultivo_detectado`, `fecha`, `proxima_revision`, `resultado` y `tratamiento`. Los tipos de las respuestas están en `src/types/diagnostico.ts`.

## Limitaciones

- **`AgenteSeguimiento` no está conectado.** La clase existe y el frontend tiene su componente (`EvolutionCard.tsx`), pero `app.py` todavía no la invoca. Además su `ORDEN_SEVERIDAD` espera `sano`/`leve`/`moderado`/`severo` y los agentes responden `Leve`, `Media`, `Alta`, `Crítica` y `Desconocida`, así que toda comparación caería al valor por defecto y devolvería `sin_cambios`. Hay que arreglar las dos cosas antes de conectarlo.
- **Salida de los agentes sin validar.** Los módulos devuelven el texto del modelo tal cual; quien llama hace `json.loads()`. Una respuesta no válida se convierte en un `500`.
- **El enrutamiento por cultivo depende de LM Studio.** Donde no esté accesible, toda foto cae al agente general sin avisar.
- **Modo debug.** `app.py` arranca Flask con `debug=True`, solo apto para desarrollo local.
- **Datasets y pesos `.pt` fuera del repositorio**, excluidos por `.gitignore` dada su magnitud.
