import { type RouteConfig, index, route, layout, prefix } from '@react-router/dev/routes'

export default [
  // index('./pages/index/index.tsx'),
  route('/sign-in', './pages/auth/sign-in.tsx'),
  route('/sign-up', './pages/auth/sign-up.tsx'),
  route('/forgot-password', './pages/auth/forgot-password.tsx'),

  // root dashboard layout
  layout('./components/layout/root-layout.tsx', [
    // index
    index('./pages/index/index.tsx'),

    ...prefix('/agents', [
      index('./pages/agents/index.tsx'),
      route(':agentId', './pages/agents/detail.tsx'),
    ]),

    // chat layout
    ...prefix('/chat/:agentId?/:threadId?', [
      index('./pages/chat/index.tsx'),
    ]),

    ...prefix('/knowledge', [
      index('./pages/knowledge/index.tsx'),
      route(':knowledgeId', './pages/knowledge/detail.tsx'),
      route(':knowledgeId/documents', './pages/knowledge/documents.tsx'),
      layout('./pages/knowledge/detail/ui/layout.tsx', [
        route(':knowledgeId/document', './pages/knowledge/detail/document.tsx'),
        route(':knowledgeId/document/:documentId/chunk', './pages/knowledge/detail/chunk.tsx'),
        route(':knowledgeId/application', './pages/knowledge/detail/application.tsx'),
        route(':knowledgeId/setting', './pages/knowledge/detail/setting.tsx'),
        route(':knowledgeId/analytics', './pages/knowledge/analytics.tsx'),
        route(':knowledgeId/runs/:runId', './pages/knowledge/detail/run-detail.tsx'),
      ]),
    ]),

    // workflow module route.
    ...prefix('/workflow', [
      index('./pages/workflow/index.tsx'),
      layout('./pages/workflow/detail/ui/layout.tsx', [
        route(':id/build?', './pages/workflow/detail/build.tsx'),
        route(':id/log', './pages/workflow/detail/log.tsx'),
        route(':id/monitor', './pages/workflow/detail/monitor.tsx'),
        route(':id/publish', './pages/workflow/detail/publish.tsx'),
        route(':id/setting', './pages/workflow/detail/setting.tsx'),
      ]),
    ]),

    ...prefix('/tasks', [
      index('./pages/tasks/index.tsx'),
      route(':taskId', './pages/tasks/detail.tsx'),
    ]),

    ...prefix('/observability', [
      index('./pages/observability/index.tsx'),
      route('runs', './pages/run/index.tsx'),
      route('runs/:runId', './pages/run/detail.tsx'),
      route('feedback', './pages/system/feedback.tsx'),
      route('monitor', './pages/system/monitor.tsx'),
    ]),

    // legacy aliases kept for active browser sessions during the IA cutover.
    ...prefix('/system', [
      route('*', './pages/system/legacy-redirect.tsx'),
    ]),

    // plugin module route.
    ...prefix('/plugins', [
      index('./pages/plugin/index.tsx'),
      // layout('./pages/plugin/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/plugin/detail/build.tsx'),
      // ]),
    ]),

    ...prefix('/plugin', [
      route('*', './pages/plugin/legacy-redirect.tsx'),
    ]),

    // model module route.
    ...prefix('/models', [
      index('./pages/model/index.tsx'),
      // layout('./pages/model/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/model/detail/build.tsx'),
      // ]),
    ]),

    ...prefix('/model', [
      route('*', './pages/model/legacy-redirect.tsx'),
    ]),

    route('/notifications', './pages/notifications/index.tsx'),

    // setting module route.
    ...prefix('/settings', [
      layout('./pages/setting/index.tsx', [
        index('./pages/setting/item/index.tsx'),
        route('account', './pages/setting/item/account.tsx'),
        route('team', './pages/setting/item/team.tsx'),
        route('lang', './pages/setting/item/lang.tsx'),
        route('api', './pages/setting/item/api.tsx'),
        route('security', './pages/setting/item/security.tsx'),
        route('secrets', './pages/setting/item/secrets.tsx'),
        route('privacy', './pages/setting/item/privacy.tsx'),
        route('billing', './pages/setting/item/billing.tsx'),
        route('notifications', './pages/setting/item/notifications.tsx'),
        route('appearance', './pages/setting/item/appearance.tsx'),
        route('analytics', './pages/setting/item/analytics.tsx'),
        route('about', './pages/setting/item/about.tsx'),
      ]),
    ]),

    ...prefix('/setting', [
      route('*', './pages/setting/legacy-redirect.tsx'),
    ]),

    // route('/welcome', './pages/welcome/welcome.tsx'),
  ]),
] satisfies RouteConfig
