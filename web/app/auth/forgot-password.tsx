import { ResetAside } from '@/auth/ui/auth-aside'
import { AuthShell } from '@/auth/ui/auth-shell'
import { ForgotPasswordForm } from '@/auth/ui/forgot-password-form'

export default function ForgotPasswordPage() {
  return (
    <AuthShell aside={<ResetAside />}>
      <ForgotPasswordForm />
    </AuthShell>
  )
}
