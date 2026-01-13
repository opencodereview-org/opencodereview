"""Test that all example files validate correctly."""

from pathlib import Path

import pytest

from opencodereview import load, Review


# Find all example files
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
YAML_EXAMPLES = list(EXAMPLES_DIR.glob("yaml/*.yaml"))
JSON_EXAMPLES = list(EXAMPLES_DIR.glob("json/*.json"))
XML_EXAMPLES = list(EXAMPLES_DIR.glob("xml/*.xml"))


@pytest.mark.parametrize("example_file", YAML_EXAMPLES, ids=lambda p: p.name)
def test_yaml_examples_validate(example_file: Path):
    """Each YAML example should load and validate successfully."""
    review = load(example_file)
    assert isinstance(review, Review)
    assert review.version == "0.1"
    assert isinstance(review.activities, list)


@pytest.mark.parametrize("example_file", JSON_EXAMPLES, ids=lambda p: p.name)
def test_json_examples_validate(example_file: Path):
    """Each JSON example should load and validate successfully."""
    review = load(example_file)
    assert isinstance(review, Review)
    assert review.version == "0.1"


@pytest.mark.parametrize("example_file", XML_EXAMPLES, ids=lambda p: p.name)
def test_xml_examples_validate(example_file: Path):
    """Each XML example should load and validate successfully."""
    review = load(example_file)
    assert isinstance(review, Review)
    assert review.version == "0.1"
    assert isinstance(review.activities, list)


def test_minimal_example_structure():
    """Test the minimal example has expected structure."""
    minimal = EXAMPLES_DIR / "yaml" / "00-minimal.yaml"
    if not minimal.exists():
        pytest.skip("Minimal example not found")

    review = load(minimal)
    assert len(review.activities) >= 1
    activity = review.activities[0]
    assert activity.category is not None


def test_human_ai_collaboration_example():
    """Test the human-AI collaboration example has expected structure."""
    collab = EXAMPLES_DIR / "yaml" / "01-human-ai-collaboration.yaml"
    if not collab.exists():
        pytest.skip("Collaboration example not found")

    review = load(collab)

    # Should have activities from both humans and agents
    authors = [a.author for a in review.activities if a.author]
    agent_authors = [a for a in authors if a.type == "agent"]
    human_authors = [a for a in authors if a.type != "agent"]

    assert len(agent_authors) > 0, "Should have agent activities"
    assert len(human_authors) > 0, "Should have human activities"


def test_security_audit_example():
    """Test the security audit example has expected structure."""
    audit = EXAMPLES_DIR / "yaml" / "02-security-audit.yaml"
    if not audit.exists():
        pytest.skip("Security audit example not found")

    review = load(audit)

    # Should have audit subject type
    assert review.subject is not None
    assert review.subject.type == "audit"
    assert review.subject.scope is not None

    # Should have security findings
    security_activities = [a for a in review.activities if a.category == "security"]
    assert len(security_activities) > 0


def test_computed_status():
    """Test that status is computed correctly from activities."""
    from opencodereview import Review, StatusChange, Comment

    # Default status is active
    review = Review(activities=[])
    assert review.status == "active"

    # After merge activity, status is merged
    review = Review(
        activities=[
            Comment(category="note", content="test"),
            StatusChange(category="merged"),
        ]
    )
    assert review.status == "merged"

    # Reopened resets to active
    review = Review(
        activities=[
            StatusChange(category="merged"),
            StatusChange(category="reopened"),
        ]
    )
    assert review.status == "active"


def test_computed_reviewers():
    """Test that reviewers are computed from assigned activities."""
    from opencodereview import Review, Assignment

    review = Review(
        activities=[
            Assignment(category="assigned", mentions=["@alice", "@bob"]),
            Assignment(category="assigned", mentions=["@charlie", "@alice"]),
        ]
    )

    reviewers = review.reviewers
    assert "@alice" in reviewers
    assert "@bob" in reviewers
    assert "@charlie" in reviewers
    # Should deduplicate
    assert len(reviewers) == 3


def test_get_visible_activities():
    """Test filtering of superseded and retracted activities."""
    from opencodereview import Review, Comment, Retraction

    review = Review(
        activities=[
            Comment(id="c1", category="note", content="original"),
            Comment(id="c2", category="note", content="updated", supersedes=["c1"]),
            Comment(id="c3", category="note", content="to be retracted"),
            Retraction(id="r1", category="retract", addresses=["c3"]),
        ]
    )

    visible = review.get_visible_activities()
    visible_ids = [a.id for a in visible]

    assert "c1" not in visible_ids  # superseded
    assert "c2" in visible_ids
    assert "c3" not in visible_ids  # retracted
    assert "r1" in visible_ids  # retraction itself is visible


# Format conversion tests

class TestFormatConversion:
    """Test loading from one format, converting to another, and checking equality."""

    @pytest.mark.parametrize("example_file", YAML_EXAMPLES, ids=lambda p: p.name)
    def test_yaml_to_json_roundtrip(self, example_file: Path, tmp_path: Path):
        """Load YAML, save as JSON, reload and compare."""
        from opencodereview import load, dump

        # Load original YAML
        original = load(example_file)

        # Save as JSON
        json_file = tmp_path / "converted.json"
        dump(original, json_file)

        # Reload from JSON
        reloaded = load(json_file)

        # Compare
        assert_reviews_equal(original, reloaded)

    @pytest.mark.parametrize("example_file", YAML_EXAMPLES, ids=lambda p: p.name)
    def test_yaml_to_json_to_yaml_roundtrip(self, example_file: Path, tmp_path: Path):
        """Load YAML, save as JSON, reload, save as YAML, reload and compare."""
        from opencodereview import load, dump

        # Load original YAML
        original = load(example_file)

        # Save as JSON
        json_file = tmp_path / "converted.json"
        dump(original, json_file)

        # Reload from JSON
        from_json = load(json_file)

        # Save back to YAML
        yaml_file = tmp_path / "converted.yaml"
        dump(from_json, yaml_file)

        # Reload from YAML
        final = load(yaml_file)

        # Compare with original
        assert_reviews_equal(original, final)

    @pytest.mark.parametrize("example_file", JSON_EXAMPLES, ids=lambda p: p.name)
    def test_json_to_yaml_roundtrip(self, example_file: Path, tmp_path: Path):
        """Load JSON, save as YAML, reload and compare."""
        from opencodereview import load, dump

        # Load original JSON
        original = load(example_file)

        # Save as YAML
        yaml_file = tmp_path / "converted.yaml"
        dump(original, yaml_file)

        # Reload from YAML
        reloaded = load(yaml_file)

        # Compare
        assert_reviews_equal(original, reloaded)

    @pytest.mark.parametrize("example_file", XML_EXAMPLES, ids=lambda p: p.name)
    def test_xml_to_yaml_roundtrip(self, example_file: Path, tmp_path: Path):
        """Load XML, save as YAML, reload and compare."""
        from opencodereview import load, dump

        # Load original XML
        original = load(example_file)

        # Save as YAML
        yaml_file = tmp_path / "converted.yaml"
        dump(original, yaml_file)

        # Reload from YAML
        reloaded = load(yaml_file)

        # Compare
        assert_reviews_equal(original, reloaded)

    @pytest.mark.parametrize("example_file", YAML_EXAMPLES, ids=lambda p: p.name)
    def test_yaml_to_xml_roundtrip(self, example_file: Path, tmp_path: Path):
        """Load YAML, save as XML, reload and compare."""
        from opencodereview import load, dump

        # Load original YAML
        original = load(example_file)

        # Save as XML
        xml_file = tmp_path / "converted.xml"
        dump(original, xml_file)

        # Reload from XML
        reloaded = load(xml_file)

        # Compare
        assert_reviews_equal(original, reloaded)

    def test_programmatic_review_roundtrip(self, tmp_path: Path):
        """Create a review programmatically and test conversion roundtrip."""
        from opencodereview import (
            Review, Comment, Assignment, StatusChange, Verdict,
            Subject, Author, Location, dump, load
        )

        # Create a complex review
        original = Review(
            version="0.1",
            subject=Subject(
                type="patch",
                provider="github-pr",
                provider_ref="123",
                repo="owner/repo",
            ),
            activities=[
                Comment(
                    id="c1",
                    author=Author(name="Alice", email="alice@example.com"),
                    category="suggestion",
                    content="Consider using a map here",
                    location=Location(file="src/main.py", lines=[(42, 42)]),
                ),
                Comment(
                    id="c2",
                    author=Author(type="agent", name="Claude", model="opus"),
                    category="note",
                    content="Good suggestion, a map would be O(1) lookup",
                    addresses=["c1"],
                ),
                Assignment(
                    id="a1",
                    category="assigned",
                    mentions=["@bob", "@charlie"],
                ),
                Verdict(
                    id="v1",
                    author=Author(name="Bob"),
                    category="approved",
                    content="LGTM",
                ),
                StatusChange(
                    id="s1",
                    category="merged",
                ),
            ],
        )

        # YAML roundtrip
        yaml_file = tmp_path / "review.yaml"
        dump(original, yaml_file)
        from_yaml = load(yaml_file)
        assert_reviews_equal(original, from_yaml)

        # JSON roundtrip
        json_file = tmp_path / "review.json"
        dump(original, json_file)
        from_json = load(json_file)
        assert_reviews_equal(original, from_json)

        # Cross-format: YAML -> JSON -> compare
        dump(from_yaml, json_file)
        cross_converted = load(json_file)
        assert_reviews_equal(original, cross_converted)

    def test_nested_replies_roundtrip(self, tmp_path: Path):
        """Test that nested replies survive format conversion."""
        from opencodereview import Review, Comment, Author, Location, dump, load

        original = Review(
            activities=[
                Comment(
                    id="c1",
                    author=Author(name="Alice"),
                    category="question",
                    content="Why this approach?",
                    location=Location(file="src/main.py", lines=[(10, 20)]),
                    replies=[
                        Comment(
                            id="c1-r1",
                            author=Author(type="agent", name="Claude"),
                            category="note",
                            content="Let me explain...",
                            replies=[
                                Comment(
                                    id="c1-r1-r1",
                                    author=Author(name="Alice"),
                                    category="note",
                                    content="Thanks!",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        # YAML roundtrip
        yaml_file = tmp_path / "nested.yaml"
        dump(original, yaml_file)
        from_yaml = load(yaml_file)

        # Check nested structure preserved
        assert len(from_yaml.activities) == 1
        assert len(from_yaml.activities[0].replies) == 1
        assert len(from_yaml.activities[0].replies[0].replies) == 1
        assert from_yaml.activities[0].replies[0].replies[0].content == "Thanks!"

        # JSON roundtrip
        json_file = tmp_path / "nested.json"
        dump(original, json_file)
        from_json = load(json_file)

        assert_reviews_equal(from_yaml, from_json)

    def test_all_activity_types_roundtrip(self, tmp_path: Path):
        """Test that all activity types survive format conversion."""
        from opencodereview import (
            Review, Comment, ReviewMark, Resolution, Retraction,
            Mention, Assignment, StatusChange, Verdict,
            Author, Location, dump, load
        )

        original = Review(
            activities=[
                Comment(id="c1", category="note", content="A note"),
                Comment(id="c2", category="suggestion", content="A suggestion"),
                Comment(id="c3", category="issue", content="An issue", severity="warning"),
                Comment(id="c4", category="praise", content="Nice!"),
                Comment(id="c5", category="question", content="Why?"),
                Comment(id="c6", category="task", content="Do this"),
                Comment(id="c7", category="security", content="Security concern", severity="critical"),
                ReviewMark(id="rm1", category="reviewed", location=Location(file="src/main.py")),
                ReviewMark(id="rm2", category="ignored", content="Auto-generated"),
                Resolution(id="res1", category="resolved", addresses=["c3"]),
                Retraction(id="ret1", category="retract", addresses=["c1"]),
                Mention(id="m1", category="mention", mentions=["@security-team"]),
                Assignment(id="a1", category="assigned", mentions=["@alice", "@bob"]),
                StatusChange(id="sc1", category="closed"),
                StatusChange(id="sc2", category="reopened"),
                StatusChange(id="sc3", category="merged"),
                Verdict(id="v1", category="approved"),
                Verdict(id="v2", category="changes_requested", content="Fix issues first"),
                Verdict(id="v3", category="commented"),
                Verdict(id="v4", category="pending", conditions=["after CI passes"]),
            ],
        )

        # YAML roundtrip
        yaml_file = tmp_path / "all_types.yaml"
        dump(original, yaml_file)
        from_yaml = load(yaml_file)
        assert len(from_yaml.activities) == len(original.activities)

        # JSON roundtrip
        json_file = tmp_path / "all_types.json"
        dump(original, json_file)
        from_json = load(json_file)

        assert_reviews_equal(from_yaml, from_json)

        # Verify specific fields survived
        for orig_act, loaded_act in zip(original.activities, from_json.activities):
            assert orig_act.id == loaded_act.id
            assert orig_act.category == loaded_act.category


def assert_reviews_equal(r1: Review, r2: Review) -> None:
    """Assert two Review objects are semantically equal."""
    assert r1.version == r2.version
    assert r1.status == r2.status
    assert set(r1.reviewers) == set(r2.reviewers)

    # Compare subjects
    if r1.subject is None:
        assert r2.subject is None
    else:
        assert r2.subject is not None
        assert r1.subject.type == r2.subject.type
        assert r1.subject.provider == r2.subject.provider
        assert r1.subject.provider_ref == r2.subject.provider_ref

    # Compare activities
    assert len(r1.activities) == len(r2.activities)
    for a1, a2 in zip(r1.activities, r2.activities):
        assert_activities_equal(a1, a2)


def assert_activities_equal(a1, a2) -> None:
    """Assert two Activity objects are semantically equal."""
    assert a1.category == a2.category
    assert a1.id == a2.id

    # Content (optional for some types)
    if hasattr(a1, "content"):
        assert getattr(a1, "content", None) == getattr(a2, "content", None)

    # Author
    if a1.author is None:
        assert a2.author is None
    else:
        assert a2.author is not None
        assert a1.author.name == a2.author.name
        assert a1.author.type == a2.author.type

    # Location
    if a1.location is None:
        assert a2.location is None
    else:
        assert a2.location is not None
        assert a1.location.file == a2.location.file
        assert a1.location.lines == a2.location.lines

    # Lists
    assert a1.supersedes == a2.supersedes
    assert a1.addresses == a2.addresses
    assert a1.mentions == a2.mentions

    # Nested replies
    assert len(a1.replies) == len(a2.replies)
    for r1, r2 in zip(a1.replies, a2.replies):
        assert_activities_equal(r1, r2)
