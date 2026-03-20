# Frontend Structure Overview

This page summarizes the web frontend layout and main module responsibilities.

## Root Layout

```
web/
├── src/                      # Frontend source code
├── public/                   # Static assets
├── docs/                     # Frontend docs
├── build/                    # Build output
├── package.json              # Dependencies and scripts
├── react-router.config.ts    # React Router config
├── vite.config.ts            # Vite config
└── tsconfig.json             # TypeScript config
```

## src/ Layout

```
src/
├── pages/                    # Route pages
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

- `src/pages/agents`: Agent-centered workspace landing page
- `src/pages/chat`: Threaded chat execution surface
- `src/pages/workflow`: Workflow design surface
- `src/pages/knowledge`: Knowledge list, detail, documents, and analytics pages
- `src/pages/tasks`: Task execution list and task detail control surface
- `src/pages/observability`: Approval, feedback, and runtime inspection entry point
- `src/pages/plugin`: plugin management surface mounted through `/plugins`
- `src/pages/model`: model management surface mounted through `/models`
- `src/pages/setting`: settings surface mounted through `/settings`
- `src/pages/run`: Run list/detail pages mounted only through the observability route namespace
