# Frontend Structure Overview

This page summarizes the web frontend layout and where each kind of code
lives. Routes are declared in `app/routes.ts`; there is no file-system
routing, so a file under `app/` is a page only when `routes.ts` names it.

## Root Layout

```
web/
├── app/                      # Frontend source code
├── e2e/                      # Playwright tests against mocked API responses
├── e2e-real/                 # Playwright tests against a real backend (CI only)
├── public/                   # Static assets
├── scripts/                  # Build checks such as the bundle budget
├── docs/                     # Frontend docs
├── eslint.config.js          # ESLint flat config (`npm run lint`)
├── package.json              # Dependencies and scripts
├── react-router.config.ts    # React Router config (SPA mode)
├── vite.config.ts            # Vite config
└── tsconfig.json             # TypeScript config
```

## app/ Layout

```
app/
├── routes.ts                 # Every route, mapped to its module
├── root.tsx                  # Root layout, providers and error boundary
├── entry.client.tsx          # Client entry
├── app.css                   # Global styles and design tokens
├── console/                  # The operator console
│   ├── shell/                # Layout, icon rail, top bar, command palette, context panel
│   ├── routes/               # Console pages, grouped as the navigation is
│   │   ├── build/            # Agents, workflows, knowledge, plugins, models
│   │   ├── execute/          # Tasks, schedules, events
│   │   ├── observe/          # Runs, traces, evaluations, costs
│   │   ├── govern/           # Approvals, policies, audit, access, secrets, budgets
│   │   ├── redirects/        # Old URLs forwarded to their console pages
│   │   ├── overview.tsx      # Workspace overview (index route)
│   │   ├── chat.tsx          # Threaded chat
│   │   ├── settings.tsx      # Settings shell; picks the section's pane
│   │   └── settings/         # One pane per settings section
│   ├── components/           # Console building blocks (tables, tiles, modals, pagers)
│   ├── adapters/             # Hooks and helpers between services and pages
│   └── styles/               # Console stylesheet
├── auth/                     # Sign-in, sign-up and password reset pages
├── extensions/               # Edition extension points (the auth panel)
├── features/                 # Larger feature modules (workflow builder, model config)
├── system/                   # Feedback and notifications pages
├── components/               # Shared UI primitives (`ui/`) and app providers
├── services/                 # API clients, one per backend area
├── stores/                   # Zustand stores
├── hooks/                    # Shared hooks
├── i18n/                     # i18next setup and `en-US` / `zh-CN` resources
├── config/                   # Static runtime configuration
├── lib/                      # Small framework helpers
├── utils/                    # Request client, dates, auth session
├── types/                    # Shared API types
├── styles/                   # Shared styles
└── assets/                   # Icons and images
```

## Routes

| Path | Module |
|---|---|
| `/` | `console/routes/overview.tsx` |
| `/chat/:agentId?/:threadId?` | `console/routes/chat.tsx` |
| `/build/*` | `console/routes/build/` |
| `/execute/*` | `console/routes/execute/` |
| `/observe/*` | `console/routes/observe/` |
| `/govern/*` | `console/routes/govern/` |
| `/settings/:section?` | `console/routes/settings.tsx` |
| `/feedback`, `/notifications` | `system/` |
| `/sign-in`, `/sign-up`, `/forgot-password`, `/reset-password` | `auth/` |

Earlier top-level URLs such as `/agents`, `/workflow/:id` and `/tasks` redirect
to their console pages through `console/routes/redirects/`. See
[`app/console/README.md`](../app/console/README.md) for the console's rules on
data that no service provides yet.
