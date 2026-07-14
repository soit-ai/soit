# Frontend Structure Overview

This page summarizes the web frontend layout and main module responsibilities.

## Root Layout

```
web/
├── app/                      # Frontend source code
├── public/                   # Static assets
├── docs/                     # Frontend docs
├── build/                    # Build output
├── package.json              # Dependencies and scripts
├── react-router.config.ts    # React Router config
├── vite.config.ts            # Vite config
└── tsconfig.json             # TypeScript config
```

## app/ Layout

```
app/
├── routes/                    # Route pages
├── components/               # Shared components
├── services/                 # API clients and service wrappers
├── stores/                   # Zustand stores
├── hooks/                    # Custom hooks
├── styles/                   # Styles and themes
├── assets/                   # Static assets (icons, images)
├── i18n/                     # i18n configuration and resources
├── config/                   # Runtime configuration
├── constant/                 # Constants and enums
├── utils/                    # Utilities
├── types/                    # Types
├── data/                     # Static data and mocks
├── lib/                      # Third-party wrappers
├── routes.ts                 # Route definitions
├── root.tsx                  # Root layout
├── entry.client.tsx          # Client entry
└── app.css                   # Global styles
```

## Current Route Focus

- `app/routes/agents`: Agent-centered workspace landing page
- `app/routes/chat`: Threaded chat execution surface
- `app/routes/workflow`: Workflow design surface
- `app/routes/knowledge`: Knowledge list, detail, documents, and analytics pages
- `app/routes/tasks`: Task execution list and task detail control surface
- `app/routes/observe`: Approval, feedback, and runtime inspection entry point
- `app/routes/plugin`: plugin management surface mounted through `/plugins`
- `app/routes/model`: model management surface mounted through `/models`
- `app/routes/setting`: settings surface mounted through `/settings`
- `app/routes/run`: Run list/detail pages mounted only through the observe route namespace
