# Documentation Map

Every part of the TestLab documentation, grouped by section. Not sure where to begin?
Find your role first, then follow the section it points to.

## Find your path

<div class="grid cards" markdown>

-   :material-rocket-launch-outline: **I want to run a TCK**

    ---

    Install the CLI and execute a TCK or a `.tck` package.

    [:octicons-arrow-right-24: Quick start](../index.md#quick-start) ·
    [Executing Tests](../specification/walkthrough/executing-tests.md)

-   :material-file-document-edit-outline: **I want to write tests**

    ---

    Learn the YAML format and find the step that does what you need.

    [:octicons-arrow-right-24: TCK Syntax](../tck-syntax/index.md) ·
    [Step Reference](../api-reference/steps/index.md)

-   :material-certificate-outline: **I work on a conformity scenario**

    ---

    Business, developer and architecture guides for a complete test suite.

    [:octicons-arrow-right-24: Certificate Management](../tutorials/certificate-management.md)

-   :material-code-braces: **I want to extend the engine**

    ---

    Architecture, step contracts, and how to add steps and services.

    [:octicons-arrow-right-24: Developer](../developer/index.md) ·
    [Contributing](../contributing/index.md)

</div>

## Home

| Page | What it covers |
|------|----------------|
| [Welcome](../index.md) | What TestLab is, and a five-minute quick start with the `testlab` CLI |
| [Overview](overview.md) | How a test goes from YAML to a result |
| [Installation](installation.md) | Every way to install the package and the `testlab` CLI |
| Documentation Map | This page |

## Specification

The requirements specification for the TestLab module, and a guided walkthrough of its
lifecycle. The YAML authoring syntax is not part of it — see [TCK Syntax](#tck-syntax).

| Page | What it covers |
|------|----------------|
| [Introduction](../specification/index.md) | Executive summary, goals and non-goals of the specification |
| [Concepts & Terminology](../specification/specification/concepts.md) | The core layers — authoring, compilation, packaging, execution, server — and the vocabulary |
| [Functional Requirements](../specification/specification/functional-requirements.md) | What the engine must do, requirement by requirement |
| [Data Models](../specification/specification/data-models.md) | Enumerations and the authoring, compile-time and run-time models |
| [Constraints & Verification](../specification/specification/constraints.md) | Technical constraints and quality attributes |
| [Package Security](../specification/specification/security.md) | Why and how `.tck` packages are signed and encrypted |
| [Walkthrough](../specification/walkthrough/index.md) | The full lifecycle, from first test to interpreted results |
| [Writing Tests](../specification/walkthrough/writing-tests.md) | Creating a TCK project from scratch |
| [Compiling Packages](../specification/walkthrough/compiling-packages.md) | Validating tests and compiling them into a portable `.tck` |
| [Executing Tests](../specification/walkthrough/executing-tests.md) | Running packages against live connectors and reading the results |

## TCK Syntax

| Page | What it covers |
|------|----------------|
| [Syntax Reference](../tck-syntax/index.md) | The complete `v1-alpha` syntax for TCK manifests and tests |
| [Cheat Sheet](../tck-syntax/cheat-sheet.md) | A one-page quick reference for authors |

## Tutorials

| Page | What it covers |
|------|----------------|
| [Getting Started](../tutorials/index.md) | Install the package and write your first test |
| [Create a Step Executor](../tutorials/create-step-executor.md) | Implement a new step in Python |
| [Add a Service Type](../tutorials/add-service-type.md) | Add a new managed service |
| [Add an Assertion Type](../tutorials/add-assertion-type.md) | Add a new assertion operator |
| [Add a Validation Rule](../tutorials/add-validation-rule.md) | Add a new compile-time validation rule |
| [Development Workflow](../tutorials/development-workflow.md) | Run the full lint, type-check and test workflow |
| [Debugging](../tutorials/debugging.md) | Diagnose common issues |
| [CCM Conformity Testing](../tutorials/ccm-conformity-testing.md) | Run Certificate Management conformity tests against a system under test (CX-0135) |
| [Certificate Management](../tutorials/certificate-management.md) | Entry point to the [business](../tutorials/ccm-business-guide.md), [developer](../tutorials/ccm-developer-guide.md) and [architecture](../tutorials/ccm-architecture-guide.md) guides |

## API Reference

| Page | What it covers |
|------|----------------|
| [Overview](../api-reference/index.md) | The block-based test authoring system |
| [Steps](../api-reference/steps/index.md) | Every step a test can `use`, with its parameters and outputs — generated from the code |

## Developer

For engineers working on the TestLab engine itself.

| Page | What it covers |
|------|----------------|
| [Overview](../developer/index.md) | Technical handover guide to the engine |
| [Product Scope](../developer/product-scope.md) | What TestLab delivers, and what it does not |
| [Architecture](../developer/architecture.md) | The compiler, runner and server, and how they fit together |
| [AI-Assisted Development](../developer/ai-development.md) | Working with the project's AI agents |
| [Step Contracts](../developer/step-contracts.md) | The single canonical contract every step has, one name and one shape per field |
| [Contract Conflict Decisions](../developer/contract-conflict-decisions.md) · [Contract Migration Plan](../developer/contract-migration-plan.md) | How contract conflicts were settled, and the plan to migrate to them |
| [Data Models](../developer/data-models.md) | The engine's internal models |
| [Block Lifecycle](../developer/block-lifecycle.md) | How a step works, from YAML to SDK call |
| [Creating a Step](../developer/creating-a-step.md) | Conventions for adding a step |
| [Execution Events](../developer/execution-events.md) | The events the engine emits while it runs |
| [Infrastructure Bindings](../developer/infrastructure-bindings.md) | How a TCK's declared requirements are bound to a real deployment |
| [Environment Injection Analysis](../developer/environment-injection-analysis.md) | How environment and context reach a step |
| [Step Reference Drift Report](../developer/step-reference-drift-report.md) | Differences between the documented steps and their implementation |
| [Decision Records](../developer/decision-records/index.md) | The architecture decisions behind TestLab |

## Contributing

| Page | What it covers |
|------|----------------|
| [Guidelines](../contributing/index.md) | How to contribute to the project |

## Related

- [Tractus-X SDK](https://github.com/eclipse-tractusx/tractusx-sdk) — the SDK TestLab builds on
