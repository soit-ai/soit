import { Badge } from '@/components/ui/badge'
import { useTranslation } from '@/i18n'

type LogTypeBadgeProps = {
  type: 'info' | 'warning' | 'error'
}

export function LogTypeBadge({ type }: LogTypeBadgeProps) {
  const { t } = useTranslation()

  switch (type) {
    case 'info':
      return <Badge variant="outline" className="bg-blue-50 text-blue-600 border-blue-200">{t('bot.log.badges.info')}</Badge>
    case 'warning':
      return <Badge variant="outline" className="bg-yellow-50 text-yellow-600 border-yellow-200">{t('bot.log.badges.warning')}</Badge>
    case 'error':
      return <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200">{t('bot.log.badges.error')}</Badge>
    default:
      return null
  }
}

type ConversationStatusBadgeProps = {
  status: 'completed' | 'error' | 'interrupted'
}

export function ConversationStatusBadge({ status }: ConversationStatusBadgeProps) {
  const { t } = useTranslation()

  switch (status) {
    case 'completed':
      return <Badge variant="outline" className="bg-green-50 text-green-600 border-green-200">{t('bot.log.badges.completed')}</Badge>
    case 'error':
      return <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200">{t('bot.log.badges.error')}</Badge>
    case 'interrupted':
      return <Badge variant="outline" className="bg-yellow-50 text-yellow-600 border-yellow-200">{t('bot.log.badges.interrupted')}</Badge>
    default:
      return null
  }
}

type ErrorResolvedBadgeProps = {
  resolved: boolean
}

export function ErrorResolvedBadge({ resolved }: ErrorResolvedBadgeProps) {
  const { t } = useTranslation()

  return resolved
    ? <Badge variant="outline" className="bg-green-50 text-green-600 border-green-200">{t('bot.log.badges.resolved')}</Badge>
    : <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200">{t('bot.log.badges.unresolved')}</Badge>
}
