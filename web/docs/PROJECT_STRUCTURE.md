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
