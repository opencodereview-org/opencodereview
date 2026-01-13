# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

OpenCodeReview is a specification and reference implementation for a portable, tool-agnostic code review format. Reviews are first-class, version-controllable objects that live in repositories alongside code, readable by humans, tools, and AI agents.

## Development Commands

```bash
# Install dependencies (from python/ directory)
cd python && uv sync

# Install with CLI tools
cd python && uv sync --extra tools

# Run all tests
cd python && uv run pytest

# Run a single test file
cd python && uv run pytest tests/test_examples.py

# Run a specific test
cd python && uv run pytest tests/test_properties.py::test_round_trip_yaml -v

# Run with coverage
cd python && uv run pytest --cov=opencodereview

# Validate a review file against schema
cd python && uv run ocr-validate <file.yaml|file.json|file.xml>

# Convert between formats
cd python && uv run ocr-convert <input> <output>
```

## Architecture

### Core Data Model (python/src/opencodereview/models.py)

```
Review (root object)
├── version: "0.1"
├── subject: Subject (patch, commit, file, directory, audit, snapshot)
├── activities: list[Activity] (append-only stream)
├── agent_context: AgentContext (instructions for AI reviewers)
└── metadata: dict (custom extensions)
```

**Activity Types** (discriminated union via `category` field):
- Commentary: `note`, `suggestion`, `issue`, `praise`, `question`, `task`, `security`
- ReviewMark: `reviewed`, `ignored`
- Resolution: `resolved`
- Retraction: `retract`
- Attention: `mention`, `assigned`
- Status: `closed`, `merged`, `reopened`
- Verdict: `approved`, `changes_requested`, `commented`, `pending`

### Key Design Principles

1. **Append-only**: Activities are never edited or deleted, only superseded via `supersedes` or retracted via `retracts`. This enables CRDT-style merging.

2. **Computed state**: `status` and `reviewers` are derived from activities, not stored directly.

3. **Multi-format**: Identical data model for YAML (human-friendly), JSON (programmatic/JSON-LD), and XML (enterprise).

### I/O Layer (python/src/opencodereview/io.py)

- `load(path)` / `loads(content, format)`: Auto-detects format, returns `Review` object
- `dump(review, path)` / `dumps(review, format)`: Serializes to specified format
- XML has specialized parsing for nested arrays

### Testing (python/tests/)

- **test_examples.py**: Validates all example files in `examples/` load correctly
- **test_properties.py**: Property-based tests using Hypothesis for round-trip serialization
- **strategies.py**: Hypothesis strategies for generating random valid Review objects

## File Structure

- `SPEC.md`: Complete specification document
- `schema/`: JSON Schema and XSD for validation
- `linked-data/`: JSON-LD context and RDF vocabulary
- `examples/`: Reference examples in YAML, JSON, XML formats
- `python/`: Reference implementation (includes CLI tools via `[tools]` extra)
- `.reviews/`: Active review files for this repository

## Working with Reviews (.reviews/)

The `.reviews/` directory contains OpenCodeReview files tracking issues, suggestions, and their resolutions for this project.

### Reading Reviews

**Important:** Before working on the spec, schemas, or related files, always read the review files first to understand known issues and avoid duplicating work.

```bash
ls .reviews/
# Read each review file to understand open issues
```

### Adding Activities

When fixing an issue, add a `resolved` activity to the appropriate review file:

```yaml
- id: <issue-id>-resolved
  created: "<ISO-8601 timestamp>"
  category: resolved
  author:
    name: <your name>
    email: <your email>
    # For AI agents:
    type: agent
    model: <model name>
  content: |
    <Description of how the issue was fixed>
  addresses: [<issue-id>]
```

When finding new issues, append an `issue` activity:

```yaml
- id: <new-id>
  created: "<ISO-8601 timestamp>"
  category: issue
  author:
    type: agent
    name: <agent name>
    model: <model name>
  content: |
    **<Issue Title>**

    **Location:** <file and line numbers>

    <Description of the issue>

    **Impact:** <Why this matters>
  file: <path>
  lines: [[<start>, <end>]]
  severity: critical | error | warning | info
```

### Validation

Always validate after editing:

```bash
cd python && uv run ocr-validate ../.reviews/<file>.yaml
```
