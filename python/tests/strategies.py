"""Hypothesis strategies for OpenCodeReview models."""

from hypothesis import strategies as st

from opencodereview import (
    AgentContext,
    Assignment,
    Author,
    Comment,
    Location,
    Mention,
    Resolution,
    Retraction,
    Review,
    ReviewMark,
    Selector,
    StatusChange,
    Subject,
    Verdict,
)


# =============================================================================
# Primitive Strategies
# =============================================================================


@st.composite
def ids(draw):
    """Generate valid activity IDs (UUIDs or short readable IDs)."""
    # Mix of UUID-like and short readable IDs
    if draw(st.booleans()):
        # UUID format
        import uuid

        return str(uuid.uuid4())
    else:
        # Short readable ID like "c1", "review-1", "comment-abc"
        prefix = draw(st.sampled_from(["c", "r", "a", "v", "m", "comment", "review"]))
        suffix = draw(st.integers(min_value=1, max_value=9999))
        return f"{prefix}{suffix}"


@st.composite
def mentions(draw):
    """Generate @-mentions like "@alice", "@agent", "@security-team"."""
    kind = draw(st.integers(min_value=0, max_value=2))
    if kind == 0:
        # Person mention
        name = draw(st.sampled_from(["alice", "bob", "charlie", "jane", "john"]))
        return f"@{name}"
    elif kind == 1:
        # Role/team mention
        team = draw(st.sampled_from(["security-team", "reviewers", "maintainers", "qa"]))
        return f"@{team}"
    else:
        # Special mention
        return draw(st.sampled_from(["@agent", "@human", "@claude", "@gpt4"]))


@st.composite
def file_paths(draw):
    """Generate valid file paths like "src/main.py"."""
    dirs = draw(
        st.lists(
            st.sampled_from(["src", "lib", "tests", "pkg", "internal", "api", "core"]),
            min_size=0,
            max_size=3,
        )
    )
    filename = draw(
        st.sampled_from(
            [
                "main.py",
                "utils.py",
                "handler.go",
                "index.ts",
                "app.rs",
                "config.yaml",
                "README.md",
            ]
        )
    )
    if dirs:
        return "/".join(dirs) + "/" + filename
    return filename


@st.composite
def line_ranges(draw):
    """Generate valid (start, end) where 1 <= start <= end."""
    start = draw(st.integers(min_value=1, max_value=10000))
    end = draw(st.integers(min_value=start, max_value=min(start + 1000, 100000)))
    return (start, end)


# =============================================================================
# Author Strategies
# =============================================================================


@st.composite
def human_authors(draw):
    """Generate human authors with name and optional email."""
    name = draw(st.sampled_from(["Alice", "Bob", "Charlie", "Jane", "John", "Eve"]))
    email = draw(st.none() | st.just(f"{name.lower()}@example.com"))
    return Author(name=name, email=email)


@st.composite
def agent_authors(draw):
    """Generate AI agent authors."""
    name = draw(st.sampled_from(["Claude", "GPT-4", "Copilot", "CodeReviewer"]))
    model = draw(st.none() | st.sampled_from(["opus", "sonnet", "haiku", "gpt-4o"]))
    version = draw(st.none() | st.sampled_from(["4.5", "3.5", "1.0"]))
    return Author(type="agent", name=name, model=model, version=version)


@st.composite
def authors(draw):
    """Generate any valid author (human or agent)."""
    return draw(st.one_of(human_authors(), agent_authors()))


# =============================================================================
# Location Strategies
# =============================================================================


@st.composite
def selectors(draw):
    """Generate semantic code selectors."""
    selector_type = draw(st.sampled_from(["symbol", "ast", "lsp"]))
    if selector_type == "symbol":
        path = draw(
            st.sampled_from(
                [
                    "MyClass.my_method",
                    "calculate_total",
                    "UserService.authenticate",
                    "Config.timeout",
                ]
            )
        )
    elif selector_type == "ast":
        path = draw(
            st.sampled_from(
                [
                    "function_definition[name='foo']",
                    "class_definition[name='Bar']",
                    "import_statement",
                ]
            )
        )
    else:
        path = draw(
            st.sampled_from(
                [
                    "pkg::module::Struct::field",
                    "crate::lib::function",
                    "std::collections::HashMap",
                ]
            )
        )
    return Selector(type=selector_type, path=path)


@st.composite
def locations(draw):
    """Generate code locations with various combinations."""
    # At least one of file, lines, or selector should be present
    has_file = draw(st.booleans())
    has_lines = draw(st.booleans())
    has_selector = draw(st.booleans())

    # Ensure at least one is present
    if not (has_file or has_lines or has_selector):
        has_file = True

    file = draw(file_paths()) if has_file else None
    lines = (
        draw(st.lists(line_ranges(), min_size=1, max_size=5)) if has_lines else None
    )
    selector = draw(selectors()) if has_selector else None
    deleted = draw(st.none() | st.booleans()) if has_lines else None
    column = draw(st.none() | st.integers(min_value=1, max_value=200))
    column_end = (
        draw(st.none() | st.integers(min_value=column or 1, max_value=300))
        if column
        else None
    )

    return Location(
        file=file,
        lines=lines,
        selector=selector,
        deleted=deleted,
        column=column,
        column_end=column_end,
    )


# =============================================================================
# Activity Strategies (one per type)
# =============================================================================


@st.composite
def comments(draw):
    """Generate Comment activities with all 7 categories."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    category = draw(
        st.sampled_from(
            ["note", "suggestion", "issue", "praise", "question", "task", "security"]
        )
    )
    content = draw(
        st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=("Cs",)))
    )
    location = draw(st.none() | locations())
    context = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    mentions_list = draw(st.lists(mentions(), max_size=3))
    supersedes = draw(st.lists(ids(), max_size=2))
    addresses = draw(st.lists(ids(), max_size=2))
    severity = draw(
        st.none() | st.sampled_from(["info", "warning", "error", "critical"])
    )

    return Comment(
        id=activity_id,
        author=author,
        category=category,
        content=content,
        location=location,
        context=context,
        mentions=mentions_list,
        supersedes=supersedes,
        addresses=addresses,
        severity=severity,
    )


@st.composite
def review_marks(draw):
    """Generate ReviewMark activities (reviewed | ignored)."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    category = draw(st.sampled_from(["reviewed", "ignored"]))
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    location = draw(st.none() | locations())

    return ReviewMark(
        id=activity_id,
        author=author,
        category=category,
        content=content,
        location=location,
    )


@st.composite
def resolutions(draw):
    """Generate Resolution activities."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    addresses = draw(st.lists(ids(), min_size=0, max_size=5))

    return Resolution(
        id=activity_id,
        author=author,
        category="resolved",
        content=content,
        addresses=addresses,
    )


@st.composite
def retractions(draw):
    """Generate Retraction activities."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    addresses = draw(st.lists(ids(), min_size=1, max_size=5))

    return Retraction(
        id=activity_id,
        author=author,
        category="retract",
        content=content,
        addresses=addresses,
    )


@st.composite
def mention_activities(draw):
    """Generate Mention activities."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    mentions_list = draw(st.lists(mentions(), min_size=1, max_size=5))
    addresses = draw(st.lists(ids(), max_size=3))

    return Mention(
        id=activity_id,
        author=author,
        category="mention",
        content=content,
        mentions=mentions_list,
        addresses=addresses,
    )


@st.composite
def assignments(draw):
    """Generate Assignment activities."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    mentions_list = draw(st.lists(mentions(), min_size=1, max_size=5))

    return Assignment(
        id=activity_id,
        author=author,
        category="assigned",
        content=content,
        mentions=mentions_list,
    )


@st.composite
def status_changes(draw):
    """Generate StatusChange activities (closed | merged | reopened)."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    category = draw(st.sampled_from(["closed", "merged", "reopened"]))
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))

    return StatusChange(
        id=activity_id,
        author=author,
        category=category,
        content=content,
    )


@st.composite
def verdicts(draw):
    """Generate Verdict activities."""
    activity_id = draw(ids())
    author = draw(st.none() | authors())
    category = draw(
        st.sampled_from(["approved", "changes_requested", "commented", "pending"])
    )
    content = draw(st.none() | st.text(max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))))
    conditions = draw(
        st.lists(
            st.sampled_from(
                ["after CI passes", "pending review", "after fixing issues"]
            ),
            max_size=3,
        )
    )

    return Verdict(
        id=activity_id,
        author=author,
        category=category,
        content=content,
        conditions=conditions,
    )


# =============================================================================
# Composite Activity Strategies
# =============================================================================


@st.composite
def activities_without_replies(draw):
    """Generate any valid activity without nested replies."""
    return draw(
        st.one_of(
            comments(),
            review_marks(),
            resolutions(),
            retractions(),
            mention_activities(),
            assignments(),
            status_changes(),
            verdicts(),
        )
    )


@st.composite
def activities_with_replies(draw, max_depth=3):
    """Generate activities with bounded nested replies."""
    activity = draw(activities_without_replies())

    if max_depth <= 0:
        return activity

    num_replies = draw(st.integers(min_value=0, max_value=2))
    if num_replies == 0:
        return activity

    replies = [
        draw(activities_with_replies(max_depth=max_depth - 1))
        for _ in range(num_replies)
    ]
    return activity.model_copy(update={"replies": replies})


def activities():
    """Generate any valid activity (union of all types), potentially with replies."""
    return activities_with_replies(max_depth=2)


# =============================================================================
# Subject Strategies
# =============================================================================


@st.composite
def patch_subjects(draw):
    """Generate patch/PR subjects."""
    provider = draw(
        st.none()
        | st.sampled_from(["github-pr", "gitlab-mr", "gerrit", "phabricator", "diff"])
    )
    provider_ref = draw(st.none() | st.text(min_size=1, max_size=20, alphabet="0123456789"))
    repo = draw(st.none() | st.sampled_from(["owner/repo", "org/project", "user/lib"]))
    base = draw(st.none() | st.sampled_from(["main", "master", "develop"]))
    head = draw(st.none() | st.sampled_from(["feature-branch", "fix/bug", "pr-123"]))
    url = draw(st.none() | st.just("https://github.com/org/repo/pull/123"))

    return Subject(
        type="patch",
        provider=provider,
        provider_ref=provider_ref,
        repo=repo,
        base=base,
        head=head,
        url=url,
    )


@st.composite
def commit_subjects(draw):
    """Generate commit subjects."""
    commit = draw(
        st.text(min_size=40, max_size=40, alphabet="0123456789abcdef")
        | st.text(min_size=7, max_size=7, alphabet="0123456789abcdef")
    )
    return Subject(type="commit", commit=commit)


@st.composite
def file_subjects(draw):
    """Generate file subjects."""
    path = draw(file_paths())
    blob = draw(st.none() | st.text(min_size=40, max_size=40, alphabet="0123456789abcdef"))
    checksum = draw(st.none() | st.just("sha256:abc123def456"))

    return Subject(type="file", path=path, blob=blob, checksum=checksum)


@st.composite
def directory_subjects(draw):
    """Generate directory subjects."""
    path = draw(st.sampled_from(["src/", "lib/", "tests/", "pkg/internal/"]))
    tree = draw(st.none() | st.text(min_size=40, max_size=40, alphabet="0123456789abcdef"))

    return Subject(type="directory", path=path, tree=tree)


@st.composite
def audit_subjects(draw):
    """Generate audit subjects."""
    name = draw(
        st.sampled_from(
            ["Security Audit Q1", "Code Review 2024", "Architecture Assessment"]
        )
    )
    scope = draw(
        st.lists(
            st.sampled_from(["src/**", "lib/*.py", "tests/", "pkg/internal/**"]),
            min_size=1,
            max_size=5,
        )
    )
    commit = draw(st.none() | st.text(min_size=40, max_size=40, alphabet="0123456789abcdef"))

    return Subject(type="audit", name=name, scope=scope, commit=commit)


@st.composite
def snapshot_subjects(draw):
    """Generate snapshot subjects."""
    from datetime import datetime, timezone

    timestamp = draw(
        st.datetimes(
            min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)
        ).map(lambda dt: dt.replace(tzinfo=timezone.utc))
    )
    commit = draw(st.none() | st.text(min_size=40, max_size=40, alphabet="0123456789abcdef"))

    return Subject(type="snapshot", timestamp=timestamp, commit=commit)


@st.composite
def subjects(draw):
    """Generate any valid subject."""
    return draw(
        st.one_of(
            patch_subjects(),
            commit_subjects(),
            file_subjects(),
            directory_subjects(),
            audit_subjects(),
            snapshot_subjects(),
        )
    )


# =============================================================================
# Agent Context Strategies
# =============================================================================


@st.composite
def agent_contexts(draw):
    """Generate agent context configurations."""
    instructions = draw(
        st.none()
        | st.sampled_from(
            [
                "Focus on security issues.",
                "Review for performance.",
                "Check for code style compliance.",
            ]
        )
    )
    diff = draw(st.none() | st.text(max_size=1000, alphabet=st.characters(blacklist_categories=("Cs",))))
    settings = draw(
        st.none()
        | st.fixed_dictionaries(
            {
                "auto_respond": st.booleans(),
                "require_mention": st.booleans(),
            }
        )
    )

    return AgentContext(instructions=instructions, diff=diff, settings=settings)


# =============================================================================
# Review Strategies
# =============================================================================


@st.composite
def reviews(draw):
    """Generate full Review objects."""
    subject = draw(st.none() | subjects())
    activity_list = draw(st.lists(activities(), min_size=0, max_size=20))
    agent_context = draw(st.none() | agent_contexts())
    metadata = draw(st.none() | st.fixed_dictionaries({"custom_field": st.text(max_size=50)}))

    return Review(
        version="0.1",
        subject=subject,
        activities=activity_list,
        agent_context=agent_context,
        metadata=metadata,
    )


# =============================================================================
# Specialized Strategies for Testing Specific Behaviors
# =============================================================================


@st.composite
def reviews_with_supersedes_and_retracts(draw):
    """Generate reviews that have supersedes/retract relationships."""
    # Create base activities with unique IDs
    base_activities = draw(st.lists(activities_without_replies(), min_size=3, max_size=10))

    # Ensure unique IDs
    for i, activity in enumerate(base_activities):
        base_activities[i] = activity.model_copy(update={"id": f"activity-{i}"})

    result_activities = list(base_activities)

    # Randomly supersede or retract some
    num_modifications = draw(st.integers(min_value=1, max_value=min(3, len(base_activities) - 1)))

    for _ in range(num_modifications):
        target_idx = draw(st.integers(0, len(base_activities) - 1))
        target_id = base_activities[target_idx].id

        if draw(st.booleans()):
            # Add superseding activity
            new_activity = draw(comments())
            new_activity = new_activity.model_copy(
                update={"supersedes": [target_id], "id": f"supersede-{target_id}"}
            )
            result_activities.append(new_activity)
        else:
            # Add retraction
            result_activities.append(
                Retraction(
                    id=f"retract-{target_id}",
                    category="retract",
                    addresses=[target_id],
                )
            )

    return Review(activities=result_activities)


@st.composite
def deeply_nested_replies(draw, max_depth=10):
    """Generate activities with deep nesting for edge case testing."""
    activity = draw(comments())

    def add_replies(act, depth):
        if depth <= 0:
            return act
        reply = draw(comments())
        reply = add_replies(reply, depth - 1)
        return act.model_copy(update={"replies": [reply]})

    depth = draw(st.integers(min_value=1, max_value=max_depth))
    return add_replies(activity, depth)
