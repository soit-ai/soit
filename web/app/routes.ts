import { type RouteConfig, index, route, layout, prefix } from '@react-router/dev/routes'

export default [
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

    ...prefix('/skills', [
      index('./routes/skill/index.tsx'),
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
      index('./routes/tasks/index.tsx'),
      route(':taskId', './routes/tasks/detail.tsx'),
    ]),

    ...prefix('/observability', [
      index('./routes/observability/index.tsx'),
      route('runs', './routes/run/index.tsx'),
      route('runs/:runId', './routes/run/detail.tsx'),
      route('feedback', './routes/system/feedback.tsx'),
      route('monitor', './routes/system/monitor.tsx'),
    ]),

    // plugin module route.
    ...prefix('/plugins', [
      index('./routes/plugin/index.tsx'),
      // layout('./routes/plugin/detail/ui/layout.tsx', [
      //   route(':id/build?', './routes/plugin/detail/build.tsx'),
      // ]),
    ]),

    ...prefix('/mcp', [
      index('./routes/mcp/index.tsx'),
    ]),

    // model module route.
    ...prefix('/models', [
      index('./routes/model/index.tsx'),
      // layout('./routes/model/detail/ui/layout.tsx', [
      //   route(':id/build?', './routes/model/detail/build.tsx'),
      // ]),
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
