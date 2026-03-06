import { useTranslation } from '@/i18n'
import { NavLayout } from '@/components/layout/nav-layout'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { RefreshCwIcon, ShieldAlertIcon } from 'lucide-react'
import { useCallback, useState, useEffect } from 'react'

// Import safety modules.
import {
  SafeSidebar,
  SafetyGuardrail,
  SecurityAlerts,
  SensitiveWordsManager,
  AccessControl,
  UserBehavior,
  PrivacyProtection,
  AuditLogs,
  SecuritySettings,
} from './ui'

function IndexPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('guardrail')
  const [alertCount, setAlertCount] = useState(3)

  // Simulate fetching alert counts.
  useEffect(() => {
    const timer = setTimeout(() => {
      setAlertCount(Math.floor(Math.random() * 5))
    }, 30000)

    return () => clearTimeout(timer)
  }, [])

  // Handle sidebar tab changes.
  const handleTabChange = useCallback((tabId: string) => {
    setActiveTab(tabId)
  }, [])

  // Handle refresh action.
  const handleRefreshData = useCallback(() => {
    setAlertCount(Math.floor(Math.random() * 5))
  }, [])

  const renderHeader = useCallback(() => {
    return (
      <div className="flex flex-1 justify-between">
        <div className="flex items-center gap-2">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink>{t('safe.center.breadcrumb.root')}</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>{t('safe.center.title')}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className="flex gap-2">
          <Button
            size={'sm'}
            variant={'outline'}
            title={t('safe.center.refresh')}
            onClick={handleRefreshData}
          >
            <RefreshCwIcon size={16} />
          </Button>
          {alertCount > 0 && (
            <Button size={'sm'} variant={'destructive'} className="gap-1">
              <ShieldAlertIcon size={16} />
              <span>{alertCount}</span>
            </Button>
          )}
        </div>
      </div>
    )
  }, [alertCount, handleRefreshData, t])

  // Render content based on the active tab.
  const renderTabContent = useCallback(() => {
    // Handle sub-menu format (e.g. 'guardrail/guardrail-content').
    const mainTab = activeTab.split('/')[0]
    const subTab = activeTab.includes('/') ? activeTab.split('/')[1] : null

    switch (mainTab) {
      case 'guardrail':
        return <SafetyGuardrail subTab={subTab} />
      case 'alerts':
        return <SecurityAlerts subTab={subTab} />
      case 'sensitive':
        return <SensitiveWordsManager subTab={subTab} />
      case 'access':
        return <AccessControl subTab={subTab} />
      case 'user':
        return <UserBehavior subTab={subTab} />
      case 'privacy':
        return <PrivacyProtection subTab={subTab} />
      case 'audit':
        return <AuditLogs subTab={subTab} />
      case 'settings':
        return <SecuritySettings subTab={subTab} />
      default:
        return <SafetyGuardrail subTab={null} />
    }
  }, [activeTab])

  return (
    <NavLayout
      left={<SafeSidebar activeTab={activeTab} onTabChange={handleTabChange} alertCount={alertCount} />}
      header={renderHeader()}
    >
      <div className="flex flex-col gap-4 p-4">
        <div className="space-y-4">
          {renderTabContent()}
        </div>
      </div>
    </NavLayout>
  )
}

export default IndexPage
