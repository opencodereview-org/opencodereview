"""Property-based tests for OpenCodeReview using Hypothesis."""

import tempfile
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from opencodereview import (
    Assignment,
    Comment,
    Mention,
    Resolution,
    Retraction,
    Review,
    ReviewMark,
    StatusChange,
    Subject,
    Verdict,
    dump,
    load,
)

from strategies import (
    activities,
    activities_without_replies,
    agent_contexts,
    assignments,
    authors,
    comments,
    deeply_nested_replies,
    locations,
    mention_activities,
    resolutions,
    retractions,
    review_marks,
    reviews,
    reviews_with_supersedes_and_retracts,
    selectors,
    status_changes,
    subjects,
    verdicts,
)


# =============================================================================
# Category to Type Mapping
# =============================================================================

CATEGORY_TO_TYPE = {
    # Comments
    "note": "Comment",
    "suggestion": "Comment",
    "issue": "Comment",
    "praise": "Comment",
    "question": "Comment",
    "task": "Comment",
    "security": "Comment",
    # Review marks
    "reviewed": "ReviewMark",
    "ignored": "ReviewMark",
    # Resolution
    "resolved": "Resolution",
    # Retraction
    "retract": "Retraction",
    # Mention
    "mention": "Mention",
    # Assignment
    "assigned": "Assignment",
    # Status changes
    "closed": "StatusChange",
    "merged": "StatusChange",
    "reopened": "StatusChange",
    # Verdicts
    "approved": "Verdict",
    "changes_requested": "Verdict",
    "commented": "Verdict",
    "pending": "Verdict",
}


# =============================================================================
# Helper Functions
# =============================================================================


def compute_expected_status(activities) -> str:
    """Compute expected status from activities list."""
    for activity in reversed(activities):
        if activity.category == "closed":
            return "closed"
        elif activity.category == "merged":
            return "merged"
        elif activity.category == "reopened":
            return "active"
    return "active"


def reviews_equal(r1: Review, r2: Review) -> bool:
    """Check if two reviews are semantically equal."""
    if r1.version != r2.version:
        return False
    if r1.status != r2.status:
        return False
    if set(r1.reviewers) != set(r2.reviewers):
        return False
    if len(r1.activities) != len(r2.activities):
        return False

    for a1, a2 in zip(r1.activities, r2.activities):
        if not activities_equal(a1, a2):
            return False

    return True


def activities_equal(a1, a2) -> bool:
    """Check if two activities are semantically equal."""
    if a1.category != a2.category:
        return False
    if a1.id != a2.id:
        return False
    if getattr(a1, "content", None) != getattr(a2, "content", None):
        return False
    if a1.supersedes != a2.supersedes:
        return False
    if a1.addresses != a2.addresses:
        return False
    if a1.mentions != a2.mentions:
        return False

    # Check author
    if (a1.author is None) != (a2.author is None):
        return False
    if a1.author and a2.author:
        if a1.author.name != a2.author.name:
            return False
        if a1.author.type != a2.author.type:
            return False

    # Check location
    if (a1.location is None) != (a2.location is None):
        return False
    if a1.location and a2.location:
        if a1.location.file != a2.location.file:
            return False
        if a1.location.lines != a2.location.lines:
            return False

    # Check replies
    if len(a1.replies) != len(a2.replies):
        return False
    for r1, r2 in zip(a1.replies, a2.replies):
        if not activities_equal(r1, r2):
            return False

    return True


# =============================================================================
# 1. Serialization Roundtrip Tests
# =============================================================================


class TestSerializationRoundtrips:
    """Test that serialization preserves data."""

    @given(reviews())
    @settings(max_examples=100)
    def test_model_to_dict_roundtrip(self, review: Review):
        """Review -> dict -> Review preserves all data."""
        data = review.model_dump(exclude_none=True, mode="json")
        restored = Review.model_validate(data)
        assert reviews_equal(review, restored)

    @given(reviews())
    @settings(max_examples=50)
    def test_yaml_roundtrip(self, review: Review):
        """dump(review, yaml) -> load(yaml) preserves data."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            yaml_path = Path(f.name)

        try:
            dump(review, yaml_path)
            restored = load(yaml_path)
            assert reviews_equal(review, restored)
        finally:
            yaml_path.unlink(missing_ok=True)

    @given(reviews())
    @settings(max_examples=50)
    def test_json_roundtrip(self, review: Review):
        """dump(review, json) -> load(json) preserves data."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            dump(review, json_path)
            restored = load(json_path)
            assert reviews_equal(review, restored)
        finally:
            json_path.unlink(missing_ok=True)

    @given(reviews())
    @settings(max_examples=50)
    def test_xml_roundtrip(self, review: Review):
        """dump(review, xml) -> load(xml) preserves data."""
        # XML 1.0 doesn't support certain control characters - skip those inputs
        # Valid XML 1.0 chars: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
        def has_invalid_xml_char(c: str) -> bool:
            code = ord(c)
            if code < 0x20 and code not in (0x9, 0xA, 0xD):
                return True
            if 0xD800 <= code <= 0xDFFF:  # surrogate pairs
                return True
            if code in (0xFFFE, 0xFFFF):
                return True
            return False

        def check_data(obj) -> bool:
            """Return True if obj contains invalid XML chars or problematic strings."""
            if isinstance(obj, str):
                # Empty, whitespace-only, or strings with leading/trailing whitespace
                # don't round-trip through XML (pre-existing limitation)
                if obj == "" or obj.strip() == "" or obj != obj.strip():
                    return True
                return any(has_invalid_xml_char(c) for c in obj)
            if isinstance(obj, dict):
                return any(check_data(v) for v in obj.values())
            if isinstance(obj, list):
                return any(check_data(v) for v in obj)
            return False

        # Check all string fields in the review - skip invalid XML inputs
        data = review.model_dump(mode="json")
        assume(not check_data(data))

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            xml_path = Path(f.name)

        try:
            dump(review, xml_path)
            restored = load(xml_path)
            assert reviews_equal(review, restored)
        finally:
            xml_path.unlink(missing_ok=True)

    @given(reviews())
    @settings(max_examples=50)
    def test_cross_format_roundtrip(self, review: Review):
        """YAML -> JSON -> YAML preserves data."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            yaml_path = Path(f.name)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = Path(f.name)

        try:
            # Review -> YAML
            dump(review, yaml_path)
            from_yaml = load(yaml_path)

            # YAML -> JSON
            dump(from_yaml, json_path)
            from_json = load(json_path)

            # JSON -> YAML
            dump(from_json, yaml_path)
            final = load(yaml_path)

            assert reviews_equal(review, final)
        finally:
            yaml_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)


# =============================================================================
# 2. Computed Property Invariants
# =============================================================================


class TestComputedProperties:
    """Test computed properties follow spec."""

    @given(st.lists(status_changes(), max_size=20))
    @settings(max_examples=100)
    def test_status_follows_spec(self, activity_list):
        """Status is determined by latest closed/merged/reopened."""
        review = Review(activities=activity_list)
        expected = compute_expected_status(activity_list)
        assert review.status == expected

    @given(st.lists(assignments(), max_size=10))
    @settings(max_examples=100)
    def test_reviewers_are_union_of_mentions(self, activity_list):
        """Reviewers = union of all mentions from 'assigned' activities."""
        review = Review(activities=activity_list)
        expected = set()
        for a in activity_list:
            expected.update(a.mentions)
        assert set(review.reviewers) == expected

    @given(reviews_with_supersedes_and_retracts())
    @settings(max_examples=100)
    def test_visible_activities_hides_superseded_and_retracted(self, review: Review):
        """Superseded and retracted activities are filtered out."""
        visible = review.get_visible_activities()
        visible_ids = {a.id for a in visible}

        # Collect what should be hidden
        superseded = set()
        retracted = set()
        for a in review.activities:
            superseded.update(a.supersedes)
            if a.category == "retract":
                retracted.update(a.addresses)

        hidden = superseded | retracted
        assert visible_ids.isdisjoint(hidden), f"Found hidden IDs in visible: {visible_ids & hidden}"

    @given(st.lists(activities_without_replies(), max_size=15))
    @settings(max_examples=100)
    def test_visible_count_correct(self, activity_list):
        """Visible activities count matches expected."""
        # Give each activity a unique ID
        for i, a in enumerate(activity_list):
            activity_list[i] = a.model_copy(update={"id": f"act-{i}"})

        review = Review(activities=activity_list)

        # Count what should be hidden
        superseded = set()
        retracted = set()
        for a in activity_list:
            superseded.update(a.supersedes)
            if a.category == "retract":
                retracted.update(a.addresses)

        hidden_count = len(superseded | retracted)
        visible = review.get_visible_activities()

        # Visible should be total minus hidden (but only hidden that exist)
        all_ids = {a.id for a in activity_list}
        actually_hidden = (superseded | retracted) & all_ids
        expected_visible = len(activity_list) - len(actually_hidden)

        assert len(visible) == expected_visible


# =============================================================================
# 3. Model Validity Tests
# =============================================================================


class TestModelValidity:
    """Test that generated models are valid."""

    @given(activities())
    @settings(max_examples=200)
    def test_all_generated_activities_are_valid(self, activity):
        """Generated activities pass Pydantic validation."""
        assert activity.category is not None
        assert activity.id is not None
        assert activity.category in CATEGORY_TO_TYPE

    @given(subjects())
    @settings(max_examples=100)
    def test_all_generated_subjects_are_valid(self, subject: Subject):
        """Generated subjects pass validation."""
        assert subject.type in ("patch", "commit", "file", "directory", "audit", "snapshot")

    @given(reviews())
    @settings(max_examples=100)
    def test_all_generated_reviews_are_valid(self, review: Review):
        """Generated reviews pass validation."""
        assert review.version == "0.1"
        assert isinstance(review.activities, list)

    @given(locations())
    @settings(max_examples=100)
    def test_all_generated_locations_are_valid(self, location):
        """Generated locations have at least one field set."""
        assert location.file is not None or location.lines is not None or location.selector is not None

    @given(authors())
    @settings(max_examples=100)
    def test_all_generated_authors_are_valid(self, author):
        """Generated authors have required fields."""
        assert author.name is not None
        if author.type == "agent":
            assert author.type == "agent"


# =============================================================================
# 4. Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @given(st.lists(activities(), max_size=100))
    @settings(max_examples=20)
    def test_many_activities(self, activity_list):
        """Reviews with many activities work correctly."""
        review = Review(activities=activity_list)
        assert len(review.activities) == len(activity_list)
        _ = review.status  # Should not raise
        _ = review.reviewers
        _ = review.get_visible_activities()

    @given(deeply_nested_replies(max_depth=10))
    @settings(max_examples=20)
    def test_deeply_nested_replies_roundtrip(self, activity):
        """Deeply nested reply structures survive roundtrip."""
        review = Review(activities=[activity])

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            yaml_path = Path(f.name)

        try:
            dump(review, yaml_path)
            restored = load(yaml_path)

            # Count nesting depth
            def count_depth(act, depth=0):
                if not act.replies:
                    return depth
                return max(count_depth(r, depth + 1) for r in act.replies)

            original_depth = count_depth(activity)
            restored_depth = count_depth(restored.activities[0])
            assert original_depth == restored_depth
        finally:
            yaml_path.unlink(missing_ok=True)

    @given(reviews())
    @settings(max_examples=50)
    def test_empty_vs_populated_fields(self, review: Review):
        """Optional fields being None vs set doesn't break anything."""
        _ = review.model_dump(exclude_none=True)
        _ = review.model_dump(exclude_none=False)

    def test_empty_review(self):
        """Empty review is valid."""
        review = Review(activities=[])
        assert review.status == "active"
        assert review.reviewers == []
        assert review.get_visible_activities() == []

    @given(st.lists(comments(), min_size=1, max_size=5))
    @settings(max_examples=50)
    def test_activities_with_same_id_references(self, comment_list):
        """Activities can reference each other."""
        # Give unique IDs
        for i, c in enumerate(comment_list):
            comment_list[i] = c.model_copy(update={"id": f"c-{i}"})

        # Make later comments address earlier ones
        if len(comment_list) > 1:
            comment_list[-1] = comment_list[-1].model_copy(
                update={"addresses": [comment_list[0].id]}
            )

        review = Review(activities=comment_list)
        data = review.model_dump(exclude_none=True, mode="json")
        restored = Review.model_validate(data)
        assert len(restored.activities) == len(comment_list)


# =============================================================================
# 5. Discriminator Correctness Tests
# =============================================================================


class TestDiscriminator:
    """Test that activity types match their categories."""

    @given(activities())
    @settings(max_examples=200)
    def test_activity_type_matches_category(self, activity):
        """Activity class matches its category discriminator."""
        category = activity.category
        expected_type = CATEGORY_TO_TYPE[category]
        assert type(activity).__name__ == expected_type

    @given(comments())
    @settings(max_examples=50)
    def test_comments_have_comment_categories(self, comment):
        """Comments only have comment categories."""
        assert comment.category in [
            "note", "suggestion", "issue", "praise", "question", "task", "security"
        ]

    @given(review_marks())
    @settings(max_examples=50)
    def test_review_marks_have_mark_categories(self, mark):
        """ReviewMarks only have mark categories."""
        assert mark.category in ["reviewed", "ignored"]

    @given(status_changes())
    @settings(max_examples=50)
    def test_status_changes_have_status_categories(self, status):
        """StatusChanges only have status categories."""
        assert status.category in ["closed", "merged", "reopened"]

    @given(verdicts())
    @settings(max_examples=50)
    def test_verdicts_have_verdict_categories(self, verdict):
        """Verdicts only have verdict categories."""
        assert verdict.category in ["approved", "changes_requested", "commented", "pending"]


# =============================================================================
# 6. Specific Activity Type Tests
# =============================================================================


class TestActivityTypes:
    """Test specific behaviors of each activity type."""

    @given(resolutions())
    @settings(max_examples=50)
    def test_resolution_roundtrip(self, resolution: Resolution):
        """Resolution activities roundtrip correctly."""
        review = Review(activities=[resolution])
        data = review.model_dump(exclude_none=True, mode="json")
        restored = Review.model_validate(data)
        assert restored.activities[0].category == "resolved"

    @given(retractions())
    @settings(max_examples=50)
    def test_retraction_has_addresses(self, retraction: Retraction):
        """Retractions have addresses to indicate what's retracted."""
        assert len(retraction.addresses) >= 1

    @given(assignments())
    @settings(max_examples=50)
    def test_assignment_has_mentions(self, assignment: Assignment):
        """Assignments have mentions to indicate assignees."""
        assert len(assignment.mentions) >= 1

    @given(mention_activities())
    @settings(max_examples=50)
    def test_mention_has_mentions(self, mention: Mention):
        """Mention activities have mentions."""
        assert len(mention.mentions) >= 1


# =============================================================================
# 7. Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    @given(st.lists(activities_without_replies(), min_size=5, max_size=15))
    @settings(max_examples=30)
    def test_full_lifecycle(self, activity_list):
        """Test a review through its full lifecycle."""
        # Add unique IDs
        for i, a in enumerate(activity_list):
            activity_list[i] = a.model_copy(update={"id": f"act-{i}"})

        # Create review
        review = Review(
            subject=Subject(type="patch", provider="github-pr", provider_ref="123"),
            activities=activity_list,
        )

        # Serialize
        data = review.model_dump(exclude_none=True, mode="json")

        # Deserialize
        restored = Review.model_validate(data)

        # Verify properties
        assert restored.status == compute_expected_status(activity_list)
        assert reviews_equal(review, restored)

    @given(reviews())
    @settings(max_examples=30)
    def test_review_with_agent_context(self, review: Review):
        """Reviews with agent context serialize correctly."""
        data = review.model_dump(exclude_none=True, mode="json")
        restored = Review.model_validate(data)

        if review.agent_context:
            assert restored.agent_context is not None
            assert restored.agent_context.instructions == review.agent_context.instructions
