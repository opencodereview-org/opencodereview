"""Pydantic models for OpenCodeReview specification."""

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Structured author - human or agent."""

    name: str
    email: str | None = None
    type: Literal["agent"] | None = None
    model: str | None = None
    version: str | None = None


class Selector(BaseModel):
    """Semantic code element reference."""

    type: str
    path: str


class Location(BaseModel):
    """Where in the code this activity applies."""

    file: str | None = None
    lines: list[tuple[int, int]] | None = None
    selector: Selector | None = None
    deleted: bool | None = None
    column: int | None = None
    column_end: int | None = None


class ActivityBase(BaseModel):
    """Base class for all activities. Activities are APPEND-ONLY."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    author: Author | None = None
    category: str
    content: str | None = None
    location: Location | None = None
    # Flat location fields (normalized to location internally)
    file: str | None = None
    lines: list[tuple[int, int]] | None = None
    deleted: bool | None = None
    column: int | None = None
    column_end: int | None = None
    selector: Selector | None = None
    # Other fields
    context: str | None = None
    replies: list["Activity"] = []
    created: datetime | None = None
    mentions: list[str] = []
    supersedes: list[str] = []
    addresses: list[str] = []
    severity: Literal["info", "warning", "error", "critical"] | None = None
    conditions: list[str] = []

    def get_location(self) -> Location | None:
        """Get normalized location (from flat fields or location object)."""
        if self.location:
            return self.location
        if self.file or self.lines or self.selector:
            return Location(
                file=self.file,
                lines=self.lines,
                selector=self.selector,
                deleted=self.deleted,
                column=self.column,
                column_end=self.column_end,
            )
        return None


class Comment(ActivityBase):
    """A comment on code."""

    category: Literal[
        "note", "suggestion", "issue", "praise", "question", "task", "security"
    ]


class ReviewMark(ActivityBase):
    """Marks code as reviewed or ignored."""

    category: Literal["reviewed", "ignored"]


class Resolution(ActivityBase):
    """Marks activities as resolved."""

    category: Literal["resolved"]


class Retraction(ActivityBase):
    """Withdraw/retract an activity."""

    category: Literal["retract"]


class Mention(ActivityBase):
    """Explicitly request attention from someone."""

    category: Literal["mention"]


class Assignment(ActivityBase):
    """Assign reviewers to the review."""

    category: Literal["assigned"]


class StatusChange(ActivityBase):
    """Change the review status."""

    category: Literal["closed", "merged", "reopened"]


class Verdict(ActivityBase):
    """A review verdict (approval/rejection)."""

    category: Literal["approved", "changes_requested", "commented", "pending"]


Activity = Annotated[
    Union[
        Comment,
        ReviewMark,
        Resolution,
        Retraction,
        Mention,
        Assignment,
        StatusChange,
        Verdict,
    ],
    Field(discriminator="category"),
]


class Subject(BaseModel):
    """What's being reviewed."""

    type: Literal["patch", "commit", "file", "directory", "audit", "snapshot"]
    name: str | None = None
    url: str | None = None
    commit: str | None = None
    tree: str | None = None
    blob: str | None = None
    checksum: str | None = None
    branch: str | None = None
    tag: str | None = None
    ref: str | None = None
    provider: str | None = None
    provider_ref: str | None = None
    repo: str | None = None
    base: str | None = None
    head: str | None = None
    base_commit: str | None = None
    head_commit: str | None = None
    path: str | None = None
    scope: list[str] | None = None
    timestamp: datetime | None = None


class AgentContext(BaseModel):
    """Configuration for AI agents."""

    instructions: str | None = None
    diff: str | None = None
    settings: dict | None = None


class Review(BaseModel):
    """Root review object."""

    version: str = "0.1"
    subject: Subject | None = None
    activities: list[Activity] = []
    agent_context: AgentContext | None = None
    metadata: dict | None = None

    @property
    def status(self) -> str:
        """Compute status from latest status activity."""
        for activity in reversed(self.activities):
            if activity.category in ("closed", "merged", "reopened"):
                if activity.category == "closed":
                    return "closed"
                elif activity.category == "merged":
                    return "merged"
                else:
                    return "active"
        return "active"

    @property
    def reviewers(self) -> list[str]:
        """Collect reviewers from assigned activities."""
        reviewers = []
        for activity in self.activities:
            if activity.category == "assigned":
                reviewers.extend(activity.mentions)
        return list(set(reviewers))

    def get_visible_activities(self) -> list[Activity]:
        """Get activities that are not superseded or retracted."""
        superseded = set()
        retracted = set()

        for activity in self.activities:
            superseded.update(activity.supersedes)
            if activity.category == "retract":
                retracted.update(activity.addresses)

        hidden = superseded | retracted
        return [a for a in self.activities if a.id not in hidden]
