import { ModelSettings } from './model-settings'
import { IntegrationSettings } from './integration-settings'
import { DataManagement } from './data-management'

export function AdvancedSettings() {
  return (
    <div className="space-y-4">
      <ModelSettings />
      <IntegrationSettings />
      <DataManagement />
    </div>
  )
}
