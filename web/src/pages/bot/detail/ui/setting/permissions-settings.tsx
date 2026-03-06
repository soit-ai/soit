import { AccessControl } from './access-control'
import { FeaturePermissions } from './feature-permissions'

export function PermissionsSettings() {
  return (
    <div className="space-y-4">
      <AccessControl />
      <FeaturePermissions />
    </div>
  )
}
