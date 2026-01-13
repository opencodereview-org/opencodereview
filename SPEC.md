# OpenCodeReview Specification

**Version:** 0.1 (Draft)

## Abstract

OpenCodeReview is a specification for a portable, tool-agnostic code review file format. It treats review as a first-class object that exists independently of any platform (GitHub, GitLab, etc.) and can be read/written by humans, tools, and AI agents.

## Motivation

### The Agentic Coding Era

AI coding assistants are transforming software development. Tools like Cursor, GitHub Copilot, and Claude Code enable developers to produce code at unprecedented rates. However, this creates new challenges:

1. **Review Happens Too Late**: Traditional review waits for commits and PRs, but AI-generated code needs review *in-process* - before it's even committed, while it's being written in your working directory
2. **Review Bottleneck**: Human reviewers become the bottleneck when AI generates 10x the code
3. **Lost Context**: AI's reasoning about changes lives in chat logs, not with the code
4. **Platform Lock-in**: Reviews trapped in GitHub/GitLab APIs can't be accessed by AI agents

### Human-AI Collaboration

OpenCodeReview enables a new workflow where humans and AI agents collaborate on code review:

- AI agents can read the review file, understand context, and contribute comments
- Humans can verify AI suggestions, respond to questions, and make final decisions
- The conversation is preserved in a portable, version-controlled format
- No API keys, authentication, or platform integrations required

### Beyond Pull Requests

Traditional code review is tied to pull requests and diffs. OpenCodeReview supports broader use cases:

- **In-Process Review**: Review code in the working directory before committing
- **Security Audits**: Review existing code without a PR
- **Architecture Reviews**: Comment on directory structure and design
- **Onboarding**: Document code with review-style annotations
- **Continuous Review**: AI agents continuously review and flag issues

## Design Principles

1. **Progressive Complexity** - Simple problems shouldn't require complex schemas
2. **Tool-Agnostic** - Works with any VCS, editor, or platform
3. **Agent-Friendly** - AI can read/write without APIs
4. **Encoding-Agnostic** - YAML, JSON, XML are all valid encodings
5. **Portable** - Lives in the repo, version-controllable
6. **Composable** - Multiple reviews, nested threads, extensible
7. **Dual-Purpose** - Works for changesets AND static code
8. **Mergeable** - Append-only activities enable conflict-free merging

## Encodings

The spec defines a **data model**, not a file format. Valid encodings:

| Encoding | Extension | Use Case |
|----------|-----------|----------|
| YAML | `.opencodereview.yaml` | Human editing |
| JSON | `.opencodereview.json` | APIs, programmatic |
| XML | `.opencodereview.xml` | Enterprise, AI agents |

Tools should:
- Accept any encoding as input
- Preserve encoding on save
- Use YAML as default for new reviews

### JSON-LD Compatibility

JSON files can optionally include a `@context` for RDF compatibility:

```json
{
  "@context": "https://opencodereview.org/context.jsonld",
  "version": "0.1",
  "activities": [...]
}
```

## Data Model

### Root Structure

```yaml
version: "0.1"           # Required - spec version
subject: {...}           # Optional - what's being reviewed
activities: [...]        # Required - all review activities
agent_context: {...}     # Optional - AI agent configuration
metadata: {...}          # Optional - custom extensions
```

**Computed from activities (not stored):**
- **Status**: From latest `closed`/`merged`/`reopened` activity (default: `active`)
- **Reviewers**: From `assigned` activities
- **Resolution**: From `resolved` activities/replies

### Subject

What's being reviewed. Every review should be pinnable to an exact version of the code.

```yaml
subject:
  type: patch | commit | file | directory | audit | snapshot
  name: <string>         # Optional human-readable name
  url: <string>          # Optional URL to source

  # Version pinning
  commit: <sha>          # Git commit hash (40 chars)
  tree: <sha>            # Git tree hash
  blob: <sha>            # Git blob hash
  checksum: <algo:hash>  # File checksum

  # Mutable references (resolved to pinned version)
  branch: <name>
  tag: <name>
  ref: <any-ref>

  # For type: patch
  provider: github-pr | gitlab-mr | gerrit | phabricator | diff
  provider_ref: <string> # PR number, MR ID, etc.
  repo: <owner/repo>
  base: <ref>
  head: <ref>

  # For type: file | directory
  path: <path>

  # For type: audit
  scope: [<glob-patterns>]
```

### Activity

The core unit. All activities are **immutable** once created (append-only).

```yaml
- id: <uuid>             # Auto-generated, omit when creating
  author:
    name: <string>       # Required
    email: <string>      # Optional
    type: "agent"        # Set for AI agents
    model: <string>      # Agent model name

  category: <category>   # Required - see categories below
  content: <string>      # Text content (markdown supported)

  # Location (flat or nested)
  file: <path>
  lines: [[start, end], ...]  # 1-indexed, inclusive ranges
  # Or:
  location:
    file: <path>
    lines: [[start, end], ...]
    selector: {type: <string>, path: <string>}

  deleted: <bool>        # True if commenting on removed line
  column: <int>          # Column precision
  column_end: <int>

  # Append-only operations
  supersedes: [<uuid>, ...]  # Replaces these activities
  addresses: [<uuid>, ...]   # References these activities

  # Threading
  replies: [<activity>, ...]

  # Metadata
  created: <iso-datetime>
  mentions: [<string>, ...]  # @agent, @human, @name, @team
  severity: info | warning | error | critical
  conditions: [<string>, ...]  # For verdicts
  context: <string>      # Code snippet
```

### Categories

| Group | Categories | Purpose |
|-------|------------|---------|
| Commentary | `note`, `suggestion`, `issue`, `praise`, `question`, `task`, `security` | Code feedback |
| Review marks | `reviewed`, `ignored` | Mark code as seen |
| Resolution | `resolved` | Mark activity as resolved |
| Retraction | `retract` | Withdraw an activity |
| Attention | `mention`, `assigned` | Request attention / assign |
| Status | `closed`, `merged`, `reopened` | Review lifecycle |
| Verdicts | `approved`, `changes_requested`, `commented`, `pending` | Decisions |

### Agent Context

Optional configuration for AI agents:

```yaml
agent_context:
  instructions: |
    [Markdown instructions for agents]
  diff: |
    [Embedded diff for context]
  settings:
    auto_respond: <bool>
    require_mention: <bool>
```

## Mergeability

Activities are append-only, making the format CRDT-friendly.

### Operations

| Operation | How |
|-----------|-----|
| Add comment | Append new activity |
| Edit | Append with `supersedes: [old-id]` |
| Delete | Append with `category: retract`, `addresses: [ids]` |
| Resolve | Reply with `category: resolved` or standalone with `addresses` |
| Assign | Append with `category: assigned`, `mentions: [who]` |
| Close/Merge/Reopen | Append with status category |

### Merge Algorithm

```
merge(file_a, file_b):
  1. Union all activities by id
  2. Same id with different content = conflict (shouldn't happen with UUIDs)
  3. Keep all activities (even superseded, for history)
  4. Tools filter superseded/retracted when displaying
```

### Display Logic

1. Build supersession graph from `supersedes`
2. Build retraction set from `category: retract`
3. Hide superseded or retracted activities
4. Compute status from latest status activity
5. Collect reviewers from `assigned` activities
6. Show resolution from `resolved` replies/activities

**Supersedes vs Retract:**
- `supersedes`: Replacing with updated version
- `retract`: Withdrawing entirely (no replacement)

## Examples

### Minimal

```yaml
version: "0.1"
activities:
  - category: note
    content: "This looks wrong"
    file: src/main.py
    lines: [[42, 42]]
```

### Full Review

```yaml
version: "0.1"
subject:
  type: patch
  provider: github-pr
  provider_ref: "123"
  url: "https://github.com/org/repo/pull/123"
activities:
  - id: c1
    category: issue
    author: {name: "Jane", email: "jane@example.com"}
    content: "Potential null pointer"
    file: src/main.py
    lines: [[42, 42]]
    severity: error

  - id: c1-reply
    category: resolved
    author: {type: "agent", name: "Claude"}
    content: "Fixed in latest commit"
    addresses: [c1]

  - category: assigned
    author: {name: "Jane"}
    mentions: ["@security-team"]
    content: "Please review auth changes"

  - category: approved
    author: {name: "Security Team"}
    content: "LGTM"

  - category: merged
    author: {name: "Jane"}
```

## JSON-LD Vocabulary

| Term | RDF Mapping |
|------|-------------|
| `activities` | LDES stream members |
| `supersedes` | `prov:wasRevisionOf` |
| `addresses` | `schema:mentions` |
| `author` | `dcterms:creator` |
| `created` | `dcterms:created` |
| `content` | `schema:text` |
| `category` | `rdf:type` |

## References

- JSON-LD: https://json-ld.org/
- LDES: https://semiceu.github.io/LinkedDataEventStreams/
- PROV-O: https://www.w3.org/TR/prov-o/
