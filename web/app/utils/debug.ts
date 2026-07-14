export function debugLog(...args: unknown[]) {
  if (import.meta.env.DEV) {
    console.debug(...args)
  }
}
