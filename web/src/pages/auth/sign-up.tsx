import { RegisterForm } from '@/pages/auth/ui/register-form'
import { AuthShell } from '@/pages/auth/ui/auth-shell'

export default function SignUpPage() {
  return (
    <AuthShell>
      <RegisterForm />
    </AuthShell>
  )
}
