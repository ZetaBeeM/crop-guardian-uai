import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")

# Create clients to call Foundry API
project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)
openai = project.get_openai_client()


def diagnostico(imagen_b64: str, agent_name: str):
    response = openai.responses.create(
        extra_body={
            "agent_reference": {
                "name": agent_name,
                "type": "agent_reference",
            }
        },
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{imagen_b64}",
                    },
                ],
            }
        ],
    )
    return response.output_text
