
@description('AKS cluster name')
param clusterName string

@description('Location for all resources')
param location string = resourceGroup().location

@description('DNS prefix for the AKS API server')
param dnsPrefix string = '${clusterName}-dns'

@description('Kubernetes version (optional). Leave empty to use default.')
param kubernetesVersion string = ''

@description('System node pool name (<= 12 chars, alphanumeric)')
param systemPoolName string = 'sysnp'

@minValue(1)
@maxValue(100)
@description('System node count')
param systemNodeCount int = 3

@description('VM size for system nodes')
param systemNodeVmSize string = 'Standard_DS2_v2'

@description('Network plugin: "kubenet" (simple, no VNet) or "azure"')
@allowed([
  'kubenet'
  'azure'
])
param networkPlugin string = 'kubenet'

@description('Service CIDR (do not overlap future VNet CIDR if you later add one)')
param serviceCidr string = '10.0.0.0/16'

@description('DNS service IP (must be within serviceCidr)')
param dnsServiceIp string = '10.0.0.10'

@description('Enable Azure RBAC for Kubernetes authorization')
param enableAzureRbac bool = true

resource aks 'Microsoft.ContainerService/managedClusters@2024-06-01' = {
  name: clusterName
  location: location

  identity: {
    type: 'SystemAssigned'
  }

  properties: {
    dnsPrefix: dnsPrefix

    // Optional version pin; empty means "use default for region"
    kubernetesVersion: empty(kubernetesVersion) ? null : kubernetesVersion

    enableRBAC: true

    // Azure AD + Azure RBAC (recommended)
    aadProfile: enableAzureRbac ? {
      managed: true
      enableAzureRBAC: true
    } : null

    // Recommended for pod-to-Azure auth (Foundry/Search/Cosmos later)
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }

    agentPoolProfiles: [
      {
        name: systemPoolName
        mode: 'System'
        count: systemNodeCount
        vmSize: systemNodeVmSize
        osType: 'Linux'
        type: 'VirtualMachineScaleSets'
      }
    ]

    networkProfile: {
      networkPlugin: networkPlugin
      serviceCidr: serviceCidr
      dnsServiceIP: dnsServiceIp
      loadBalancerSku: 'standard'
      outboundType: 'loadBalancer'
    }
  }
}

output aksResourceId string = aks.id
output aksFqdn string = aks.properties.fqdn
output aksOidcIssuerUrl string = aks.properties.oidcIssuerProfile.issuerURL
