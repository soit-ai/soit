import type { Config } from "@react-router/dev/config";

export default {
  // Config options...
  appDirectory: "app",
  basename: "/",
  buildDirectory: "build",
  buildEnd: async ({ buildManifest }) => {
    // Custom build end logic...
  },
  // Server-side render by default, to enable SPA mode set this to `false`
  ssr: false,
} satisfies Config;
