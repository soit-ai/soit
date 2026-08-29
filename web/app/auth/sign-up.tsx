import { RegisterForm } from '@/auth/ui/register-form'
import { AuthShell } from '@/auth/ui/auth-shell'

export default function SignUpPage() {
  return (
    <AuthShell>
      <RegisterForm />
    </AuthShell>
  )
}
