import os
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_AI_AGENT1_NAME")

# Create clients to call Foundry API
project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)
openai = project.get_openai_client()

# Generate a response using the agent
response = openai.responses.create(
    extra_body={
        "agent_reference": {
            "name": AGENT_NAME,
            "type": "agent_reference",
        }
    },
    input="What is the largest city in France?",
)
print(response.output_text)
