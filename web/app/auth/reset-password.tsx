import { ResetAside } from '@/auth/ui/auth-aside'
import { AuthShell } from '@/auth/ui/auth-shell'
import { ResetPasswordForm } from '@/auth/ui/reset-password-form'

export default function ResetPasswordPage() {
  return (
    <AuthShell aside={<ResetAside />}>
      <ResetPasswordForm />
    </AuthShell>
  )
}
