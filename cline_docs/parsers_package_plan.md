# Shared Parser Package Plan

## Objective
Refactor the core parsing logic into a shared Python package that supports both CLI and Django integration, with clear interfaces and full test coverage for both modes.

---

## Proposed Structure

```
parsers_core/
├── __init__.py
├── base_parser.py         # Abstract base class/interface for all parsers
├── registry.py            # Parser registry and selection logic
├── utils.py               # Shared utilities (path, config, normalization)
├── cli_wrapper.py         # CLI entry points (wraps core logic)
├── django_adapter.py      # Django entry points/adapters
├── tests/
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_django.py
│   └── ...
└── ... (individual parser modules)
```

---

## Key Interfaces

- **BaseParser**: Abstract class with methods for initialization, parse/extract, normalize, and output.
- **Parser Registry**: Mechanism to register and select appropriate parser based on file type/metadata.
- **CLI Wrapper**: Thin layer to invoke core logic from CLI scripts (maintains current workflow).
- **Django Adapter**: Thin layer to invoke core logic from Django views, tasks, or management commands.
- **Config/Path Abstraction**: Utilities to handle environment-specific configs and paths.

---

## Integration Plan

1. **Refactor core logic** from existing scripts into `parsers_core/` modules.
2. **Implement base interfaces** and registry for parser selection.
3. **Provide CLI wrappers** to maintain current CLI workflow.
4. **Add Django adapters** for import/use in Django project.
5. **Abstract configs/paths** for portability.
6. **Set up tests** for both CLI and Django modes.
7. **Document usage** for both environments.

---

## Next Steps
- Review and refine this structure with Extractor_Dev and Greg.
- Identify any blockers or special requirements from the current codebase.
- Begin incremental refactoring and testing.

---

*Please review and suggest any changes or additions. Once agreed, we can proceed with implementation and testing.* 