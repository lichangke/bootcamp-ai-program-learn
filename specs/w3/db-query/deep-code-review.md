---
description: Perform a deep, non-destructive code review for Python and TypeScript codebases with architecture, design, and code-quality checks.
handoffs:
  - label: Plan Fixes
    agent: speckit.plan
    prompt: Create a technical plan to address the highest-severity review findings.
  - label: Implement Fixes
    agent: speckit.implement
    prompt: Implement approved fixes for the code review findings.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Run a deep code review for Python and TypeScript code, with priority on architecture and design quality, KISS, DRY/YAGNI/SOLID, function size constraints, parameter count constraints, and Builder pattern usage.

## Operating Constraints

**STRICTLY READ-ONLY**: Do **not** modify files during this command.

**Evidence-First**: Every finding must cite exact file paths and line numbers.

**High-Signal Output**: Prefer fewer, high-impact findings over exhaustive low-value comments.

## Review Scope

1. If `$ARGUMENTS` specifies paths, files, modules, or packages, review only that scope.
2. If `$ARGUMENTS` is empty, review the whole repository with emphasis on Python (`*.py`) and TypeScript (`*.ts`, `*.tsx`) production code first, then tests.
3. Exclude generated artifacts and dependency folders by default (`node_modules`, `dist`, `build`, `.venv`, `venv`, `coverage`, `.next`, `.turbo`, lockfiles, minified bundles).

## Execution Flow

1. Parse scope and collect repository context
   - Identify Python and TypeScript roots and major modules.
   - Load high-level architecture context if present (`README`, architecture docs, ADRs, `pyproject.toml`, `package.json`, `tsconfig*.json`).
2. Build a review inventory
   - Enumerate key files, public APIs, service boundaries, data models, and cross-module dependencies.
   - Identify candidate hotspots: large files, complex classes, high-churn modules, duplicated utility code.
3. Run analysis passes in the order below.

### A. Architecture and Design

Evaluate whether Python and TypeScript code follows sound architecture and design practices:

- Layering and dependency direction are clear and stable.
- Interface design is explicit and coherent.
  - Python: `Protocol`, abstract base classes, typed call contracts.
  - TypeScript: `interface`, type contracts, boundary DTOs.
- Modules are cohesive and have clear responsibilities.
- Extension points exist where variability is expected.
- Cross-cutting concerns (logging, auth, validation, errors, config) are centralized instead of scattered.
- Tight coupling, cyclic dependencies, and boundary leakage are flagged.

### B. KISS Principle

Detect over-engineering and unnecessary complexity:

- Abstractions with no clear reuse benefit.
- Excessive indirection (deep call chains, pass-through wrappers).
- Premature generalization and speculative extension hooks.
- Complex patterns where a simpler direct implementation is clearer and safer.

### C. Code Quality Rules (DRY, YAGNI, SOLID)

- **DRY**: duplicated logic, repeated branching, near-copy functions/classes.
- **YAGNI**: dead code paths, unused extension points, feature flags without active use.
- **SOLID**:
  - Single Responsibility: mixed concerns in one module/class/function.
  - Open/Closed: fragile edits required for every new case.
  - Liskov Substitution: subtype behavior breaks base assumptions.
  - Interface Segregation: overly broad interfaces forcing irrelevant methods.
  - Dependency Inversion: high-level policy directly depending on low-level details.

### D. Function and Signature Constraints

Flag and prioritize:

- Functions longer than 150 lines.
- Functions/methods with more than 7 parameters.
- Long parameter lists where a value object/config object would improve clarity.

Do not fail solely on thresholds; explain context, risk, and better alternatives.

### E. Builder Pattern Usage

Review Builder pattern use pragmatically:

- Recommend introducing a Builder when object construction is complex, has many optional fields, or requires ordered validation steps.
- Flag Builder overuse when construction is simple and direct constructors/factories are clearer.
- Check whether existing Builders preserve invariants, readability, and discoverability.
- Ensure Builder does not hide invalid states or bypass required fields.

### F. Language-Specific Best Practices

Python:

- Type hints are meaningful and consistent at boundaries.
- Errors use domain-appropriate exceptions with actionable messages.
- Resource lifecycle is safe (`with`/context manager, cleanup guarantees).
- Async usage avoids blocking calls and hidden event-loop hazards.

TypeScript:

- Strict typing is preferred over `any`; narrowing is explicit and safe.
- Public API contracts are typed and validated at boundaries.
- Async flows handle rejection paths predictably.
- Domain models avoid weakly typed object bags and ambiguous unions.

### G. Testability and Safety

- Critical logic has focused tests.
- Error and edge paths are covered.
- Architecture-critical boundaries have contract tests or equivalent safeguards.
- Refactor suggestions include a minimal safety strategy.

## Severity Model

- **CRITICAL**: architecture breakage, data corruption/security risk, or defect likely in normal operation.
- **HIGH**: design flaws or quality issues likely to cause frequent bugs or slow delivery.
- **MEDIUM**: maintainability issues with moderate risk.
- **LOW**: clarity/style improvements with low operational risk.

## Output Format

Return a Markdown report only (no file writes) using this structure:

## Deep Code Review Report

### Scope

- Reviewed paths/modules
- Exclusions applied
- Languages detected

### Findings

| ID | Severity | Category | Principle | Location | Summary | Why It Matters | Recommended Change |
|----|----------|----------|-----------|----------|---------|----------------|--------------------|

Rules:

- `Location` must include file + line (for example: `backend/src/service.py:142`).
- `Principle` should be one of: Architecture, Interface Design, Extensibility, KISS, DRY, YAGNI, SOLID-S, SOLID-O, SOLID-L, SOLID-I, SOLID-D, Function-Length, Parameter-Count, Builder, Python-Best-Practice, TypeScript-Best-Practice, Testing.
- Every recommendation must be specific and implementable.

### Metrics Snapshot

- Total findings
- Findings by severity
- Functions >150 lines (count + top offenders)
- Functions/methods with >7 parameters (count + top offenders)
- Builder opportunities (count)
- Suspected Builder overuse cases (count)
- DRY duplication clusters (count)

### Priority Fix Plan

1. Top 3-5 changes that reduce the most risk first.
2. Quick wins (low effort, high impact).
3. Deferred improvements with rationale.

### Positive Notes

- List concrete strengths worth preserving.

### Open Questions

- List only blocking ambiguities that materially affect recommendations.

## Review Rules

- Be strict on correctness and design quality, practical on style.
- Prefer actionable improvements over generic criticism.
- Do not invent missing requirements; when uncertain, state assumptions explicitly.
- If no significant issues are found, explicitly state: `No high-signal issues found in reviewed scope.` and include residual risks.

## Context

$ARGUMENTS
