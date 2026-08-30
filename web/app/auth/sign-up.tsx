import { SignUpAside } from '@/auth/ui/auth-aside'
import { AuthShell } from '@/auth/ui/auth-shell'
import { RegisterForm } from '@/auth/ui/register-form'

export default function SignUpPage() {
  return (
    <AuthShell aside={<SignUpAside />}>
      <RegisterForm />
    </AuthShell>
  )
}
