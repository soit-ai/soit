# kernel/registry

In-process registry for runtime lookup of versioned artifacts (plugins, tools, templates).

- Thread-safe dictionary-based implementation (`registry.py`)
- Singleton accessors (`deps.py`)
- Integrity helpers (`signature.py`)

This registry is a **runtime view**, not the source of truth.
The source of truth remains DB/filesystem; the registry is populated during installation/startup.
