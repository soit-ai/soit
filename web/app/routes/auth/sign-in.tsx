import { LoginForm } from '@/routes/auth/ui/login-form'
import { AuthShell } from '@/routes/auth/ui/auth-shell'

export default function LoginPage() {
  return (
    <AuthShell>
      <LoginForm />
    </AuthShell>
  )
}
