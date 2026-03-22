import { ForgotPasswordForm } from '@/routes/auth/ui/forgot-password-form'
import { AuthShell } from '@/routes/auth/ui/auth-shell'

export default function ForgotPasswordPage() {
  return (
    <AuthShell>
      <ForgotPasswordForm />
    </AuthShell>
  )
}
