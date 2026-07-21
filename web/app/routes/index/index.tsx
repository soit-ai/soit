import { NavLayout } from '@/components/layout/nav-layout'

import { useHomeDashboard } from './hooks/use-home-dashboard'
import { FocusPanel } from './ui/focus-panel'
import { HomeHero } from './ui/home-hero'
import { OperationsDashboard } from './ui/operations-dashboard'
import { PlatformMap } from './ui/platform-map'
import { SectionHeading } from './ui/section-heading'

export function meta() {
  return [
    { title: 'SOIT Agent Workspace' },
    {
      name: 'description',
      content: 'SOIT 工作区首页，集中查看 Agent、Knowledge、Workflow、Task 与 Runs 运行状态。',
    },
  ]
}

export default function HomePage() {
  const dashboard = useHomeDashboard()

  return (
    <NavLayout className="bg-transparent">
      <main className="mx-auto flex w-full max-w-[1520px] flex-1 flex-col gap-8 px-4 pb-8 pt-5 md:px-6 xl:px-8">
        <HomeHero
          summary={dashboard.summary}
          isRefreshing={dashboard.isRefreshing}
          onRefresh={dashboard.refetchAll}
          partialFailure={dashboard.partialFailure}
          isInitialError={dashboard.isInitialError}
        />

        <SectionHeading
          eyebrowKey="agent.home.sections.capabilityEyebrow"
          titleKey="agent.home.sections.capabilityTitle"
          descriptionKey="agent.home.sections.capabilityDescription"
        />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,0.76fr)]">
          <PlatformMap summary={dashboard.summary} />
          <FocusPanel
            summary={dashboard.summary}
            agents={dashboard.newestAgents}
            tasks={dashboard.attentionTasks}
            knowledgeBases={dashboard.recentKnowledge}
            isLoading={dashboard.isInitialLoading}
          />
        </div>

        <SectionHeading
          eyebrowKey="agent.home.sections.metricsEyebrow"
          titleKey="agent.home.sections.metricsTitle"
          descriptionKey="agent.home.sections.metricsDescription"
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

