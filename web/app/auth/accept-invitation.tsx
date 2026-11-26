import { AcceptInvitationCard } from '@/auth/ui/accept-invitation-card'
import { SignUpAside } from '@/auth/ui/auth-aside'
import { AuthShell } from '@/auth/ui/auth-shell'

export default function AcceptInvitationPage() {
  return (
    <AuthShell aside={<SignUpAside />}>
      <AcceptInvitationCard />
    </AuthShell>
  )
}
