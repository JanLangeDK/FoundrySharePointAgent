#!/usr/bin/env sh

set -eu

resource_group="${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP before provisioning}"
location="${AZURE_LOCATION:-francecentral}"

az group create --name "$resource_group" --location "$location" --output none
deployment=$(az deployment group create \
  --resource-group "$resource_group" \
  --template-file infra/search.bicep \
  --parameters location="$location" \
  --query properties.outputs \
  --output json)

search_endpoint=$(printf '%s' "$deployment" | jq -r '.searchEndpoint.value')
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AZURE_SEARCH_ENDPOINT "$search_endpoint"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AZURE_SEARCH_INDEX_NAME "sharepoint-documents"

printf 'Azure AI Search endpoint: %s\n' "$search_endpoint"