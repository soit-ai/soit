import { ThemeSettings } from './theme-settings'
import { ChatInterfaceSettings } from './chat-interface-settings'
import { AvatarSettings } from './avatar-settings'

interface StyleSettingsProps {
  botInfo: {
    name: string;
    avatar: string;
  }
}

export function StyleSettings({ botInfo }: StyleSettingsProps) {
  return (
    <div className="space-y-4">
      <ThemeSettings />
      <ChatInterfaceSettings botInfo={botInfo} />
      <AvatarSettings botInfo={botInfo} />
    </div>
  )
}
