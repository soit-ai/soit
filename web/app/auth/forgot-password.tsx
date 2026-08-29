import { ForgotPasswordForm } from '@/auth/ui/forgot-password-form'
import { AuthShell } from '@/auth/ui/auth-shell'

export default function ForgotPasswordPage() {
  return (
    <AuthShell>
      <ForgotPasswordForm />
    </AuthShell>
  )
}
