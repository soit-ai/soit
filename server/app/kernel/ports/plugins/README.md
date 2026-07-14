# plugins port

This port defines how plugin runtimes execute tools and resolve skills exported by installed plugins.

- The marketplace installs a plugin (package + manifest/spec) into a tenant/workspace scope.
- Plugin installation projects exported tools into the runtime registry as concrete `tool_ref` entries.
- Agent and Workflow execution bind and invoke those concrete tools through **ToolPort**.
- The canonical execution path is `Agent/Workflow -> ToolPort -> RegistryToolRouterPort -> PluginRuntimePort`.
- Plugin-installed skills are resolved by `PluginRuntimePort.resolve_skill_context(...)` and injected into the Agent runtime request as governed context.
- `PluginRuntimePort` is a runtime adapter boundary only. Agents do not execute plugins directly; plugins provide, install, and govern tools or skills.
