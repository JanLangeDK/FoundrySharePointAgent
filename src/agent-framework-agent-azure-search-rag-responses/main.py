# Copyright (c) Microsoft. All rights reserved.

import asyncio
import logging
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import load_dotenv

from secure_search import SharePointSearchContextProvider

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def _resolved_env(name: str) -> str:
    """Return an env var value, treating un-substituted ``${VAR}`` / ``{{VAR}}`` placeholders as empty.

    Hosted-agent runtimes that perform template substitution on ``agent.yaml`` /
    ``agent.manifest.yaml`` may leave the literal ``${VAR}`` or ``{{VAR}}`` text
    when ``VAR`` is undefined at deploy time (e.g. CI smoke runs that don't
    provision an Azure Search index). The sample should treat that case the
    same as "unset" so the agent still starts and responds — just without the
    optional RAG capability.
    """
    value = os.environ.get(name, "").strip()
    if (value.startswith("${") and value.endswith("}")) or (
        value.startswith("{{") and value.endswith("}}")
    ):
        return ""
    return value


async def main():
    credential = AzureCliCredential() if os.getenv("AZURE_AUTH_MODE") == "cli" else DefaultAzureCredential()

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    search_endpoint = _resolved_env("AZURE_SEARCH_ENDPOINT")
    search_index_name = _resolved_env("AZURE_SEARCH_INDEX_NAME")
    context_providers = []
    if not (search_endpoint and search_index_name):
        logger.warning(
            "Azure Search environment variables are not fully set. "
            "The agent will start, but search functionality will be unavailable."
        )
    else:
        # Connect to a pre-provisioned Azure AI Search index. The index is expected to
        # exist and contain documents with the schema described in README.md
        # (id / content / sourceName / sourceLink). The context provider runs a search
        # against this index before each model invocation and injects the matching
        # documents into the model context.
        search_provider = SharePointSearchContextProvider(
            source_id="sharepoint_search_rag",
            endpoint=search_endpoint,
            index_name=search_index_name,
            credential=credential,
            mode="semantic",
            top_k=10,
        )
        context_providers.append(search_provider)


    agent = Agent(
        client=client,
        instructions=(
            "You answer questions only from the provided SharePoint context. "
            "If the context does not contain the answer, say that you could not find it. "
            "Cite each source using its sourceName and sourceLink. Never infer or reveal "
            "documents that are not present in the retrieved context. If the context contains "
            "NO_AUTHORIZED_RESULTS, refuse to answer from general knowledge and do not invent citations."
        ),
        context_providers=context_providers,
        # History will be managed by the hosting infrastructure, thus there
        # is no need to store history by the service. Learn more at:
        # https://developers.openai.com/api/reference/resources/responses/methods/create
        default_options={"store": False},
    )
    server = ResponsesHostServer(agent)
    await server.run_async()
    if context_providers:
        await context_providers[0].close()

if __name__ == "__main__":
    asyncio.run(main())
