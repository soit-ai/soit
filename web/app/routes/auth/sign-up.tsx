import { RegisterForm } from '@/routes/auth/ui/register-form'
import { AuthShell } from '@/routes/auth/ui/auth-shell'

export default function SignUpPage() {
  return (
    <AuthShell>
      <RegisterForm />
    </AuthShell>
  )
}
