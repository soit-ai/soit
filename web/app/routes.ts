import { type RouteConfig, index, route, layout, prefix } from '@react-router/dev/routes'

/**
 * The console is the application. It was built in parallel under `/v2` and now
 * takes the root; `app/routes_old/` keeps the pre-rebuild tree for one release
 * so anything the console has not absorbed is still recoverable from git rather
 * than only from history.
 *
 * Two families of redirect keep old links working: the `/v2/*` paths this
 * rebuild used while it was parallel, and the pre-rebuild paths that the new
 * information architecture renamed.
 */
export default [
  // Auth sits outside the console shell, and outside the backup: it is live
  // code the rebuild never replaced.
  route('/sign-in', './auth/sign-in.tsx'),
  route('/sign-up', './auth/sign-up.tsx'),
  route('/forgot-password', './auth/forgot-password.tsx'),

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
    // Product feedback predates the rebuild and the prototype has no page for
    // it, so it keeps its own translations and lives outside app/console —
    // which is prototype-derived by definition — while still rendering inside
    // the shell, because the rail links here.
    route('feedback', './system/feedback.tsx'),
    route('_kitchen', './console/routes/kitchen.tsx'),
  ]),

  // Pre-rebuild paths the new information architecture renamed, plus the
  // parallel-development `/v2` prefix. Both carry query and hash through.
  route('/v2/*', './console/routes/redirects/v2.tsx'),
  route('/agents', './console/routes/redirects/agents.tsx'),
  route('/agents/:agentId', './console/routes/redirects/agent-detail.tsx'),
  route('/knowledge', './console/routes/redirects/knowledge.tsx'),
  route('/knowledge/:knowledgeId', './console/routes/redirects/knowledge-detail.tsx'),
  route('/workflow', './console/routes/redirects/workflow.tsx'),
  route('/workflow/:id/*', './console/routes/redirects/workflow-detail.tsx'),
  route('/plugins', './console/routes/redirects/plugins.tsx'),
  route('/models/*', './console/routes/redirects/models.tsx'),
  route('/tasks', './console/routes/redirects/tasks.tsx'),
  route('/tasks/:taskId', './console/routes/redirects/task-detail.tsx'),
  route('/observe/audits', './console/routes/redirects/audits.tsx'),
] satisfies RouteConfig
