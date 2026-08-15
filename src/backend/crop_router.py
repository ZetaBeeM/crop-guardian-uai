"""
Enruta una foto de cultivo hacia el agente de diagnostico de Azure AI
Foundry correspondiente.

Un modelo multimodal local (LM Studio, zero-shot) clasifica el cultivo de
la foto antes de gastar tokens en la nube, lo que ademas permite usar un
agente con instrucciones/lista de enfermedades acotadas al cultivo
detectado. Si el modelo local no da una prediccion clara -o no esta
disponible- se enruta al agente general.
"""

import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_MODEL = "google/gemma-4-e4b"

CROPS = ["Cerezas", "Tomates", "Uvas"]
GENERAL = "General"

# Nombre del agente de Azure AI Foundry a usar por cultivo. AZURE_AI_AGENT2_NAME
# se reserva para el agente de tratamiento (tratamiento_agent.py).
AGENT_ENV_VARS = {
    GENERAL: "AZURE_AI_AGENT1_NAME",
    "Tomates": "AZURE_AI_AGENT3_NAME",
    "Uvas": "AZURE_AI_AGENT4_NAME",
    "Cerezas": "AZURE_AI_AGENT5_NAME",
}

PROMPT = (
    "Estas viendo una foto de una planta o cultivo agricola. Identifica a "
    f"cual de estos cultivos pertenece: {', '.join(CROPS)}. "
    "Responde unicamente con el nombre exacto de una de esas opciones, "
    "sin texto adicional."
)

client = OpenAI(base_url=LMSTUDIO_BASE_URL, api_key="lm-studio")


def extract_crop(respuesta: str) -> str | None:
    # El modelo local suele ignorar la instruccion de responder solo con el
    # nombre y razona en voz alta mencionando cada opcion antes de decidir,
    # asi que se toma la mencion mas a la derecha del texto como la
    # respuesta final en vez de confiar en el texto completo.
    last_match, last_pos = None, -1
    for crop in CROPS:
        for m in re.finditer(re.escape(crop), respuesta, flags=re.IGNORECASE):
            if m.start() > last_pos:
                last_pos = m.start()
                last_match = crop
    return last_match


def clasificar_cultivo(imagen_b64: str) -> str:
    """Devuelve el nombre del cultivo detectado por el modelo local, o
    GENERAL si no hay una prediccion clara o LM Studio no esta disponible
    (para no bloquear el diagnostico por un problema del clasificador local).
    """
    try:
        response = client.chat.completions.create(
            model=LMSTUDIO_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{imagen_b64}"
                            },
                        },
                    ],
                }
            ],
            temperature=0,
        )
    except Exception:
        return GENERAL

    respuesta = response.choices[0].message.content.strip()
    return extract_crop(respuesta) or GENERAL


def agente_para_cultivo(cultivo: str) -> str:
    """Devuelve el nombre del agente de Azure AI Foundry configurado para
    el cultivo dado, usando el agente general como fallback."""
    env_var = AGENT_ENV_VARS.get(cultivo, AGENT_ENV_VARS[GENERAL])
    agent_name = os.getenv(env_var)
    if not agent_name:
        raise RuntimeError(f"Falta configurar la variable de entorno {env_var} en .env")
    return agent_name
