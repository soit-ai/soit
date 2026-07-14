import type { Config } from "@react-router/dev/config";

export default {
  // Config options...
  appDirectory: "app",
  basename: "/",
  buildDirectory: "build",
  buildEnd: async ({ buildManifest }) => {
    // Custom build end logic...
  },
  future: {
    v8_middleware: true,
    v8_splitRouteModules: true,
    v8_viteEnvironmentApi: true,
    v8_passThroughRequests: true,
    v8_trailingSlashAwareDataRequests: true,
  },
  // Server-side render by default, to enable SPA mode set this to `false`
  ssr: false,
} satisfies Config;
