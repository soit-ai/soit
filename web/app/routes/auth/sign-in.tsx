import { AuthPanel } from '@/extensions/auth'
import { AuthShell } from '@/routes/auth/ui/auth-shell'

export default function LoginPage() {
  return (
    <AuthShell>
      <AuthPanel />
    </AuthShell>
  )
}
