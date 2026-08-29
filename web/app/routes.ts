import { type RouteConfig, index, route, layout, prefix } from '@react-router/dev/routes'

export default [
  // Console v2 (v13 prototype rebuild) — parallel tree under /v2 until switch-over (P7).
  ...prefix('/v2', [
    layout('./console/shell/console-layout.tsx', [
      index('./console/routes/overview.tsx'),
      route('chat/:agentId?/:threadId?', './console/routes/chat.tsx'),
      ...prefix('build', [
        route('agents', './console/routes/build/agents.tsx'),
        route('agents/:id', './console/routes/build/agent-detail.tsx'),
        route('workflows', './console/routes/build/workflows.tsx'),
        route('workflows/new', './console/routes/build/workflow-new.tsx'),
        route('workflows/:id', './console/routes/build/workflow-detail.tsx'),
        route('knowledge', './console/routes/build/knowledge.tsx'),
        route('knowledge/new', './console/routes/build/knowledge-new.tsx'),
        route('knowledge/:id', './console/routes/build/knowledge-detail.tsx'),
        route('plugins', './console/routes/build/plugins.tsx'),
        route('models', './console/routes/build/models.tsx'),
      ]),
      ...prefix('execute', [
        route('tasks', './console/routes/execute/tasks.tsx'),
        route('tasks/:id', './console/routes/execute/task-detail.tsx'),
        route('schedules', './console/routes/execute/schedules.tsx'),
        route('events', './console/routes/execute/events.tsx'),
      ]),
      ...prefix('observe', [
        route('runs', './console/routes/observe/runs.tsx'),
        route('runs/:id', './console/routes/observe/run-detail.tsx'),
        route('traces', './console/routes/observe/traces.tsx'),
        route('traces/:traceId', './console/routes/observe/trace-detail.tsx'),
      ]),
      ...prefix('govern', [
        route('approvals', './console/routes/govern/approvals.tsx'),
        route('policies', './console/routes/govern/policies.tsx'),
        route('audit', './console/routes/govern/audit.tsx'),
        route('secrets', './console/routes/govern/secrets.tsx'),
      ]),
      route('settings/:section?', './console/routes/settings.tsx'),
      route('_kitchen', './console/routes/kitchen.tsx'),
    ]),
  ]),

  // index('./routes/index/index.tsx'),
  route('/sign-in', './routes/auth/sign-in.tsx'),
  route('/sign-up', './routes/auth/sign-up.tsx'),
  route('/forgot-password', './routes/auth/forgot-password.tsx'),

  // root dashboard layout
  layout('./components/layout/root-layout.tsx', [
    // index
    index('./routes/index/index.tsx'),

    ...prefix('/agents', [
      index('./routes/agents/index.tsx'),
      route(':agentId', './routes/agents/detail.tsx'),
    ]),

    // chat layout
    ...prefix('/chat/:agentId?/:threadId?', [
      index('./routes/chat/index.tsx'),
    ]),

    ...prefix('/knowledge', [
      index('./routes/knowledge/index.tsx'),
      route(':knowledgeId', './routes/knowledge/detail.tsx'),
      route(':knowledgeId/documents', './routes/knowledge/documents.tsx'),
      layout('./routes/knowledge/detail/ui/layout.tsx', [
        route(':knowledgeId/document', './routes/knowledge/detail/document.tsx'),
        route(':knowledgeId/document/:documentId/chunk', './routes/knowledge/detail/chunk.tsx'),
        route(':knowledgeId/usages', './routes/knowledge/detail/usages.tsx'),
        route(':knowledgeId/setting', './routes/knowledge/detail/setting.tsx'),
        route(':knowledgeId/analytics', './routes/knowledge/analytics.tsx'),
        route(':knowledgeId/runs/:runId', './routes/knowledge/detail/run-detail.tsx'),
      ]),
    ]),

    // workflow module route.
    ...prefix('/workflow', [
      index('./routes/workflow/index.tsx'),
      layout('./routes/workflow/detail/ui/layout.tsx', [
        route(':id/build?', './routes/workflow/detail/build.tsx'),
        route(':id/log', './routes/workflow/detail/log.tsx'),
        route(':id/monitor', './routes/workflow/detail/monitor.tsx'),
        route(':id/publish', './routes/workflow/detail/publish.tsx'),
        route(':id/setting', './routes/workflow/detail/setting.tsx'),
      ]),
    ]),

    ...prefix('/tasks', [
      layout('./routes/tasks/layout.tsx', [
        index('./routes/tasks/index.tsx'),
        route('processing', './routes/tasks/processing.tsx'),
        route(':taskId', './routes/tasks/detail.tsx'),
      ]),
    ]),

    ...prefix('/observe', [
      index('./routes/observe/index.tsx'),
      route('audits', './routes/run/audits.tsx'),
      route('runs', './routes/run/index.tsx'),
      route('runs/:runId', './routes/run/detail.tsx'),
    ]),

    route('/feedback', './routes/system/feedback.tsx'),
    route('/search', './routes/search/index.tsx'),
    route('/diagnostics', './routes/system/monitor.tsx'),

    // plugin module route.
    ...prefix('/plugins', [
      index('./routes/plugin/index.tsx'),
      // layout('./routes/plugin/detail/ui/layout.tsx', [
      //   route(':id/build?', './routes/plugin/detail/build.tsx'),
      // ]),
    ]),

    // model module route.
    ...prefix('/models', [
      layout('./routes/model/layout.tsx', [
        index('./routes/model/index.tsx'),
        route('overview', './routes/model/overview.tsx'),
        route('library', './routes/model/library.tsx'),
        route('providers', './routes/model/providers.tsx'),
      ]),
    ]),

    route('/notifications', './routes/notifications/index.tsx'),

    // setting module route.
    ...prefix('/settings', [
      layout('./routes/setting/index.tsx', [
        index('./routes/setting/item/index.tsx'),
        route('account', './routes/setting/item/account.tsx'),
        route('team', './routes/setting/item/team.tsx'),
        route('lang', './routes/setting/item/lang.tsx'),
        route('api', './routes/setting/item/api.tsx'),
        route('security', './routes/setting/item/security.tsx'),
        route('secrets', './routes/setting/item/secrets.tsx'),
        route('privacy', './routes/setting/item/privacy.tsx'),
        route('billing', './routes/setting/item/billing.tsx'),
        route('notifications', './routes/setting/item/notifications.tsx'),
        route('appearance', './routes/setting/item/appearance.tsx'),
        route('analytics', './routes/setting/item/analytics.tsx'),
        route('about', './routes/setting/item/about.tsx'),
      ]),
    ]),

    // route('/welcome', './routes/welcome/welcome.tsx'),
  ]),
] satisfies RouteConfig
