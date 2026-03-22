# plugins port

This port defines how the core system invokes tools provided by installed plugins.

- The marketplace installs a plugin (package + manifest/spec) into a tenant/workspace scope.
- The runtime invokes plugin-provided tools via a **PluginRuntimePort** implementation.
