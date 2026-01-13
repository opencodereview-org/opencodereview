# OpenCodeReview

A portable, tool-agnostic specification for code review as a first-class object.

## Why OpenCodeReview?

### The Problem

**Review happens too late.** Traditional code review waits until code is committed and a PR is opened. But when AI generates code, you need to review it *before* committing - in your working directory, in-process, as it's being written.

**Review fatigue is real.** As AI coding assistants generate more code faster, the review burden shifts entirely to humans. A developer using Cursor, Copilot, or Claude can produce 10x the code - but someone still needs to review it all.

**Platform lock-in fragments reviews.** Your review comments live in GitHub, GitLab, or Gerrit - inaccessible to tools, trapped in proprietary APIs, lost when you switch platforms.

**AI agents can't participate.** Current review systems require API access, authentication, and platform-specific integrations. An AI agent can't simply read a file and understand the review context.

**Context gets lost.** When an AI modifies code, the reasoning behind changes lives in chat logs, not alongside the code. Reviewers lack context about *why* changes were made.

### The Solution

OpenCodeReview treats **review as a first-class object** - a portable file that:

- Lives in your repo alongside the code
- Can be read/written by humans, tools, and AI agents alike
- Captures the full conversation: comments, responses, resolutions, verdicts
- Enables **human-AI collaboration** on code review
- Works across platforms without lock-in

### Use Cases

- **In-Process Review**: Review AI-generated code before committing - in your working directory, as it's written
- **Agentic Code Review**: AI agents review code and leave comments; humans verify and respond
- **Review Handoff**: Export reviews from one platform, import to another
- **Async Collaboration**: AI and humans collaborate asynchronously via the review file
- **Audit Trail**: Permanent, version-controlled record of all review activity
- **Static Analysis**: Security audits, architecture reviews without a PR/diff

## Overview

OpenCodeReview defines a data model for capturing code reviews that:

- **Works anywhere** - YAML, JSON, or XML encoding
- **Supports any workflow** - Changeset reviews (PRs, commits) and static code reviews (audits, security reviews)
- **Is agent-friendly** - AI can read/write reviews without APIs
- **Merges cleanly** - Append-only activities enable conflict-free collaboration
- **Lives in your repo** - Portable, version-controllable review files

## Quick Example

```yaml
version: "0.1"
subject:
  type: patch
  provider: github-pr
  provider_ref: "123"
activities:
  - category: issue
    author: {name: "Jane"}
    content: "Potential null pointer here"
    file: src/main.py
    lines: [[42, 42]]
  - category: approved
    author: {name: "Jane"}
    content: "LGTM after fixing the null check"
```

## Documentation

- [SPEC.md](SPEC.md) - Full specification
- [examples/](examples/) - Example files in all formats
- [schema/](schema/) - JSON Schema and XSD for validation

## Key Concepts

### Everything is an Activity

Comments, verdicts, assignments, status changes - all are immutable activities appended to a stream:

| Category | Purpose |
|----------|---------|
| `note`, `suggestion`, `issue`, `praise`, `question`, `task`, `security` | Commentary |
| `reviewed`, `ignored` | Mark code as seen |
| `resolved` | Mark activity as resolved |
| `retract` | Withdraw an activity |
| `mention`, `assigned` | Request attention / assign reviewers |
| `closed`, `merged`, `reopened` | Review lifecycle |
| `approved`, `changes_requested`, `commented`, `pending` | Verdicts |

### Append-Only Mergeability

Activities are never edited or deleted - only superseded or retracted:

```yaml
# Edit by superseding
- id: new-id
  supersedes: [old-id]
  content: "Updated comment"

# Delete by retracting
- category: retract
  addresses: [activity-to-remove]
```

This makes git merges trivial - just union the activities by ID.

### Computed State

Status, reviewers, and resolution are computed from activities, not stored as fields:
- **Status**: Latest `closed`/`merged`/`reopened` activity (default: `active`)
- **Reviewers**: Collected from `assigned` activities
- **Resolved**: Has reply or reference with `category: resolved`

## Encodings

The same data model works in multiple formats:

| Format | Extension | Use Case |
|--------|-----------|----------|
| YAML | `.opencodereview.yaml` | Human editing |
| JSON | `.opencodereview.json` | APIs, programmatic |
| XML | `.opencodereview.xml` | Enterprise, AI agents |

JSON files can optionally include `@context` for JSON-LD/RDF compatibility.

## Libraries

- [Python](python/) - Reference implementation with Pydantic models

## License

MIT
