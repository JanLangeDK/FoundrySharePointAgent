# Copyright (c) Microsoft. All rights reserved.

"""Provision the Azure AI Search index used by the SharePoint agent.

Creates the permission-aware chunk index documented in README.md. Existing
indexes are validated and left untouched when their schema is compatible.

Usage (from this directory, with the venv activated and ``az login`` done):

    python provision_index.py

Required env vars (also read from a local ``.env`` file if present):

    AZURE_SEARCH_ENDPOINT      e.g. https://<your-search>.search.windows.net
    AZURE_SEARCH_INDEX_NAME    e.g. sharepoint-documents

Your identity needs ``Search Service Contributor`` (to create the index) and
``Search Index Data Contributor`` (to upload documents) on the search service.
"""

import asyncio
import os

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import AzureCliCredential, DefaultAzureCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,  # pyright: ignore[reportUnknownVariableType]
    SearchFieldDataType,
    SearchIndex,
    SimpleField,  # pyright: ignore[reportUnknownVariableType]
)
from dotenv import load_dotenv

REQUIRED_FIELDS = {
    "id",
    "content",
    "sourceName",
    "sourceLink",
    "sourceItemId",
    "sourceETag",
    "sourceRoot",
    "chunkIndex",
    "allowedPrincipals",
}


def build_index(name: str) -> SearchIndex:
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="standard.lucene"),
            SimpleField(name="sourceName", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SimpleField(name="sourceLink", type=SearchFieldDataType.String, retrievable=True),
            SimpleField(name="sourceItemId", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SimpleField(name="sourceETag", type=SearchFieldDataType.String, retrievable=True),
            SimpleField(name="sourceRoot", type=SearchFieldDataType.String, filterable=True, retrievable=True),
            SimpleField(name="chunkIndex", type=SearchFieldDataType.Int32, filterable=True, retrievable=True),
            SimpleField(
                name="allowedPrincipals",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
                retrievable=False,
            ),
        ],
    )


async def main() -> None:
    load_dotenv()

    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    credential = AzureCliCredential() if os.getenv("AZURE_AUTH_MODE") == "cli" else DefaultAzureCredential()

    async with (
        credential,
        SearchIndexClient(endpoint=endpoint, credential=credential) as index_client,
    ):
        index = build_index(index_name)
        try:
            existing_index = await index_client.get_index(index_name)
            existing_fields = {field.name for field in existing_index.fields}
            missing_fields = REQUIRED_FIELDS - existing_fields
            if missing_fields:
                raise RuntimeError(
                    f"Index '{index_name}' is missing fields {sorted(missing_fields)}. "
                    "Delete and recreate this development index before syncing SharePoint."
                )
            print(f"Index '{index_name}' already exists with a compatible schema.")
        except ResourceNotFoundError:
            print(f"Creating index '{index_name}'...")
            await index_client.create_index(index)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
