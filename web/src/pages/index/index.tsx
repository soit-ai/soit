import { NavLayout } from '@/components/layout/nav-layout'

import { useHomeDashboard } from './hooks/use-home-dashboard'
import { FocusPanel } from './ui/focus-panel'
import { HomeHero } from './ui/home-hero'
import { OperationsDashboard } from './ui/operations-dashboard'
import { PlatformMap } from './ui/platform-map'
import { SectionHeading } from './ui/section-heading'

export function meta() {
  return [
    { title: 'SOIT Workspace' },
    {
      name: 'description',
      content: 'SOIT 工作区首页，集中查看 Agent、Knowledge、Workflow、Task 与 Runs 运行状态。',
    },
  ]
}

export default function HomePage() {
  const dashboard = useHomeDashboard()

  return (
    <NavLayout className="bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.12),_transparent_28%),linear-gradient(180deg,rgba(248,250,252,0.98)_0%,rgba(241,245,249,0.96)_100%)] dark:bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.12),_transparent_24%),linear-gradient(180deg,rgba(10,15,25,0.98)_0%,rgba(12,18,30,0.96)_100%)]">
      <main className="mx-auto flex w-full max-w-[1480px] flex-1 flex-col gap-6 p-4 md:p-6 xl:p-8">
        <HomeHero
          summary={dashboard.summary}
          isRefreshing={dashboard.isRefreshing}
          onRefresh={dashboard.refetchAll}
          partialFailure={dashboard.partialFailure}
        />

        <SectionHeading
          eyebrowKey="app.home.sections.capabilityEyebrow"
          titleKey="app.home.sections.capabilityTitle"
          descriptionKey="app.home.sections.capabilityDescription"
        />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.58fr)_minmax(340px,0.72fr)]">
          <div className="flex min-w-0 flex-col gap-6">
            <PlatformMap summary={dashboard.summary} />
          </div>

          <div className="flex min-w-0 flex-col gap-6">
            <FocusPanel
              summary={dashboard.summary}
              agents={dashboard.newestAgents}
              tasks={dashboard.attentionTasks}
              knowledgeBases={dashboard.recentKnowledge}
              isLoading={dashboard.isInitialLoading}
            />
          </div>
        </div>

        <SectionHeading
          eyebrowKey="app.home.sections.metricsEyebrow"
          titleKey="app.home.sections.metricsTitle"
          descriptionKey="app.home.sections.metricsDescription"
        />

        <OperationsDashboard
          summary={dashboard.summary}
          agents={dashboard.agents}
          workflows={dashboard.workflows}
          knowledgeBases={dashboard.knowledgeBases}
          tasks={dashboard.tasks}
          runs={dashboard.runs}
          isLoading={dashboard.isInitialLoading}
        />
      </main>
    </NavLayout>
  )
}
