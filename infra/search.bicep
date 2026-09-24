targetScope = 'resourceGroup'

@description('Azure region for the Search service.')
param location string = resourceGroup().location

@description('Globally unique Azure AI Search service name.')
param searchServiceName string = 'srch-${uniqueString(subscription().id, resourceGroup().id, 'sharepoint-rag')}'

@allowed([
  'basic'
  'standard'
])
@description('Azure AI Search SKU. Basic is suitable for development.')
param searchSku string = 'basic'

resource searchService 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: searchSku
  }
  properties: {
    disableLocalAuth: true
    hostingMode: 'Default'
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    replicaCount: 1
    semanticSearch: 'disabled'
  }
  tags: {
    application: 'FoundrySharePointAgent'
    dataClassification: 'sharepoint-documents'
  }
}

output searchServiceId string = searchService.id
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
