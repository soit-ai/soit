import { ForgotPasswordForm } from '@/pages/auth/ui/forgot-password-form'
import { AuthShell } from '@/pages/auth/ui/auth-shell'

export default function ForgotPasswordPage() {
  return (
    <AuthShell>
      <ForgotPasswordForm />
    </AuthShell>
  )
}
