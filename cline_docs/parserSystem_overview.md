# Parser System Overview

## Structure & Flow
- **Main Locations:**
  - `app/parser/`: Main parsing logic, orchestration, and entry points.
  - `dataextractai/parsers/`: Specialized extractors and parser classes for different document types.

## Invocation Methods
- Django management commands (batch processing)
- Direct function calls (from Django views or tasks)
- CLI scripts (standalone operation)

## Typical Flow
1. **Input:** PDF or data file is provided (upload, CLI, or batch job).
2. **Parser Selection:** System determines which parser class/module to use based on file type or metadata.
3. **Extraction:** Parser extracts structured data (regex, ML, or rule-based logic).
4. **Normalization:** Data is normalized and mapped to internal models.
5. **Persistence:** Data is saved to the database (Django ORM) or returned as a structured object.

## Key Entry Points
- `app/parser/main.py` or `parser.py`: Main orchestration logic.
- `dataextractai/parsers/`: Each file/class is responsible for a specific document type or extraction method.

## Dependencies & Modularization
- Some utility functions and models are tightly coupled to Django settings and ORM.
- File paths and configs may be hardcoded and need abstraction for portability.
- Modularization may require refactoring for settings, adapters, and test coverage.

## Recommendations for Collaboration
- Start with a feature branch for modularization.
- Identify and decouple hard dependencies.
- Abstract configs and paths.
- Add minimal tests for both environments.

---

Let me know if you need code snippets, diagrams, or deeper dives into any part of the system! 