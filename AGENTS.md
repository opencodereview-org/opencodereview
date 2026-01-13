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
