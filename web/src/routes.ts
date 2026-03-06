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

    // chat layout
    ...prefix('/chat/:appId?/:id?', [
      index('./pages/chat/index.tsx'),
    ]),

    // bot module route.
    ...prefix('/bot', [
      index('./pages/bot/index.tsx'),
      layout('./pages/bot/detail/ui/layout.tsx', [
        route(':id/build?', './pages/bot/detail/build.tsx'),
        route(':id/log', './pages/bot/detail/log.tsx'),
        route(':id/monitor', './pages/bot/detail/monitor.tsx'),
        route(':id/publish', './pages/bot/detail/publish.tsx'),
        route(':id/setting', './pages/bot/detail/setting.tsx'),
      ]),
    ]),

    // dataset module route.
    ...prefix('/dataset', [
      index('./pages/dataset/index.tsx'),
      // layout('./pages/dataset/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/dataset/detail/build.tsx'),
      // ]),
      layout('./pages/dataset/detail/ui/layout.tsx', [
        route(':datasetId/document', './pages/dataset/detail/document.tsx'),
        route(':datasetId/document/:documentId/chunk', './pages/dataset/detail/chunk.tsx'),
        route(':datasetId/log', './pages/dataset/detail/log.tsx'),
        route(':datasetId/monitor', './pages/dataset/detail/monitor.tsx'),
        route(':datasetId/publish', './pages/dataset/detail/publish.tsx'),
        route(':datasetId/setting', './pages/dataset/detail/setting.tsx'),
        route(':datasetId/application', './pages/dataset/detail/application.tsx'),
        route(':datasetId/crawler', './pages/dataset/detail/crawler.tsx'),
        route(':datasetId/analytics', './pages/dataset/detail/analytics.tsx'),
        route(':datasetId/runs/:runId', './pages/dataset/detail/run-detail.tsx'),
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

    // run module route.
    ...prefix('/run', [
      index('./pages/run/index.tsx'),
      route(':runId', './pages/run/detail.tsx'),
    ]),

    // plugin module route.
    ...prefix('/plugin', [
      index('./pages/plugin/index.tsx'),
      // layout('./pages/plugin/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/plugin/detail/build.tsx'),
      // ]),
    ]),

    // model module route.
    ...prefix('/model', [
      index('./pages/model/index.tsx'),
      // layout('./pages/model/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/model/detail/build.tsx'),
      // ]),
    ]),

    // safe module route.
    ...prefix('/safe', [
      index('./pages/safe/index.tsx'),
      // layout('./pages/safe/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/safe/detail/build.tsx'),
      // ]),
    ]),

    // store module route.
    ...prefix('/store', [
      index('./pages/store/index.tsx'),
      // layout('./pages/store/detail/ui/layout.tsx', [
      //   route(':id/build?', './pages/store/detail/build.tsx'),
      // ]),
    ]),

    // system module route.
    ...prefix('/system', [
      route('feedback', './pages/system/feedback.tsx'),
      route('monitor', './pages/system/monitor.tsx'),
    ]),

    route('/notifications', './pages/notifications/index.tsx'),

    // setting module route.
    ...prefix('/setting', [
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

    // route('/welcome', './pages/welcome/welcome.tsx'),
  ]),

  // only app layout
  layout('./components/layout/app-layout.tsx', [
    route('/app/:type?/:id?', './pages/app/index.tsx'),
  ]),
] satisfies RouteConfig
