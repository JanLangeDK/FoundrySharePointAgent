# Foundry SharePoint RAG Agent

A Python Microsoft Agent Framework agent that answers from SharePoint documents indexed in Azure AI Search. It uses the Foundry Responses protocol so it can later be published to Teams and Microsoft 365 Copilot.

## Confirmed Azure context

- Tenant domain: `<your-tenant>.onmicrosoft.com`
- Tenant ID: `<your-tenant-id>`
- Foundry project: `<your-project>` in `<your-region>`
- Foundry endpoint: `https://<your-foundry>.services.ai.azure.com/api/projects/<your-project>`
- Current model deployment: `gpt-4.1-mini`
- Azure AI Search: `<your-search>` (`basic`, API keys disabled)
- Search index: `sharepoint-documents`
- Ingestion app client ID: `<ingestion-app-client-id>`

`gpt-4.1-mini` is already deployed and works for initial development, but Azure currently marks this model version as legacy. Prefer a current small GPT model such as `gpt-5.4-mini` before production rollout.

## Architecture

1. A SharePoint ingestion process reads documents and ACLs.
2. Azure AI Search stores document chunks with `allowedPrincipals`, a collection of Entra user and group object IDs.
3. The channel integration resolves the caller to trusted Entra principal IDs.
4. `SharePointSearchContextProvider` applies an OData ACL filter before any document text reaches the model.
5. Microsoft Agent Framework sends only authorized context to the Foundry model and returns source citations.

Retrieval fails closed when no trusted principal mapping exists. A Foundry `x-agent-user-id` is a stable platform identity, but it is not an Entra object ID. The Teams/Copilot integration must populate `FOUNDRY_USER_PRINCIPAL_MAP_JSON`, or replace that static mapping with a trusted identity resolver, before production use.

## Project layout

- `azure.yaml`: Foundry hosted-agent definition
- `infra/search.bicep`: RBAC-only Azure AI Search service
- `scripts/provision-search.sh`: deploys Search and updates the active `azd` environment
- `src/agent-framework-agent-azure-search-rag-responses/main.py`: agent host
- `src/agent-framework-agent-azure-search-rag-responses/secure_search.py`: permission-aware retrieval
- `src/agent-framework-agent-azure-search-rag-responses/sharepoint_source.py`: SharePoint URL parser
- `src/agent-framework-agent-azure-search-rag-responses/sync_sharepoint.py`: Graph-to-Search synchronizer
- `src/agent-framework-agent-azure-search-rag-responses/provision_index.py`: Search index schema
- `.vscode/launch.json`: F5 debugging with Agent Inspector

## Search index contract

Each indexed chunk must contain:

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | `Edm.String` | Unique chunk key |
| `content` | `Edm.String` | Searchable document text |
| `sourceName` | `Edm.String` | Citation title |
| `sourceLink` | `Edm.String` | SharePoint URL |
| `sourceItemId` | `Edm.String` | Microsoft Graph drive item ID |
| `sourceETag` | `Edm.String` | SharePoint item version |
| `sourceRoot` | `Edm.String` | Configured synchronization root |
| `chunkIndex` | `Edm.Int32` | Chunk position within the file |
| `allowedPrincipals` | `Collection(Edm.String)` | Filterable Entra user/group object IDs |

The synchronizer refreshes content and effective ACLs, then removes stale chunks for deleted or inaccessible files.

## Local setup

The agent source requires Python 3.13. Its environment has already been locked with `uv`.

```bash
cd src/agent-framework-agent-azure-search-rag-responses
uv sync --frozen --python 3.13
uv run --no-sync pytest -q
```

To test against Search locally, set the Search endpoint in `.env`, then explicitly opt into a development identity:

```env
ALLOW_LOCAL_DEVELOPMENT_IDENTITY=true
LOCAL_DEVELOPMENT_PRINCIPAL_IDS=<entra-user-object-id>,<entra-group-object-id>
```

Never enable `ALLOW_LOCAL_DEVELOPMENT_IDENTITY` in a deployed environment. Press `F5` to start the agent and open Foundry Toolkit Agent Inspector.

Local agent and F5 runs set `AZURE_AUTH_MODE=cli` so model and Search calls use your developer identity. SharePoint synchronization separately uses the certificate identity configured in `.env`.

## Provision Search

The Search Bicep disables API keys and uses Microsoft Entra authentication only.

```bash
./scripts/provision-search.sh
```

Grant the ingestion identity `Search Service Contributor` and `Search Index Data Contributor`. Grant the deployed agent managed identity `Search Index Data Reader`.

## SharePoint ingestion

The configured source is the root site library at:

```text
https://<your-tenant>.sharepoint.com/Shared Documents
```

The supplied AllItems URL is stored in `SHAREPOINT_FOLDER_URL`. The synchronizer resolves the site and drive IDs at runtime, recursively reads the selected library, extracts common Office/PDF/text formats, and writes permission-filtered chunks to Search.

The first successful synchronization indexed 1,354 chunks from 3 source files with zero skipped files.

The certificate-based `FoundrySharePointAgent-Ingestion` app has only the tenant-wide Graph role `Sites.Selected` and a `fullcontrol` assignment on this one site. FullControl is required to enumerate complete effective ACLs; the synchronizer itself performs only read operations against SharePoint. Set these standard `DefaultAzureCredential` variables locally or in the ingestion job:

```env
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<ingestion-app-client-id>
AZURE_CLIENT_CERTIFICATE_PATH=<certificate-pem-path>
```

The local certificate is under ignored `.certs/` and expires on September 24, 2027. Rotate it before expiry and store the production certificate in a managed secret/certificate store.

The ingestion identity also needs `Search Service Contributor` while creating the index and `Search Index Data Contributor` while synchronizing documents.

After Search is provisioned and both permission sets are assigned:

```bash
cd src/agent-framework-agent-azure-search-rag-responses
AZURE_AUTH_MODE=cli uv run --no-sync python provision_index.py
uv run --no-sync python sync_sharepoint.py
```

Supported files: `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.html`, `.txt`, `.md`, `.csv`, `.json`, and `.xml`. Files larger than `SHAREPOINT_MAX_FILE_BYTES` are skipped.

Permission handling is fail-closed:

- Entra users and groups are stored by object ID.
- SharePoint-only groups are stored as `siteGroup:<id>` and must also be supplied by the future Teams/Copilot identity resolver.
- Organization-wide sharing links are stored as `tenant:<tenant-id>`.
- Anonymous links and permissions without a supported principal are not indexed.

The recommended production pattern is:

1. Use an Entra application with certificate authentication and `Sites.Selected` access limited to the required site.
2. Read files and effective permissions through Microsoft Graph.
3. Resolve SharePoint users and groups to Entra object IDs.
4. Chunk files, populate the index contract above, and use merge-or-upload for idempotent refreshes.
5. Process deletions and ACL changes on every synchronization cycle.

Avoid tenant-wide `Sites.Read.All` unless the ingestion scope genuinely requires it.

## Foundry deployment

`azd` must be authenticated to the intended tenant, and the active environment must be bound to the selected Foundry project and model deployment.

Deployment is intentionally not run yet. Once SharePoint ingestion and identity mapping are configured, use the Microsoft Foundry deployment workflow.
