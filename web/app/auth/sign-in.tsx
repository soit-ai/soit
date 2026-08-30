import { AuthPanel } from '@/extensions/auth'
import { SignInAside } from '@/auth/ui/auth-aside'
import { AuthShell } from '@/auth/ui/auth-shell'

export default function LoginPage() {
  return (
    <AuthShell aside={<SignInAside />}>
      <AuthPanel />
    </AuthShell>
  )
}
