import { LoginForm } from '@/pages/auth/ui/login-form'
import { AuthShell } from '@/pages/auth/ui/auth-shell'

export default function LoginPage() {
  return (
    <AuthShell>
      <LoginForm />
    </AuthShell>
  )
}
