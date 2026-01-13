# OpenCodeReview Python Library

Python library for the [OpenCodeReview](https://opencodereview.org) specification.

## Installation

```bash
pip install opencodereview
```

## Usage

```python
from opencodereview import load, dump, Review, Comment, Author

# Load a review file
review = load("review.yaml")

# Access activities
for activity in review.activities:
    print(f"{activity.category}: {activity.content}")

# Check computed status
print(f"Status: {review.status}")
print(f"Reviewers: {review.reviewers}")

# Create a review programmatically
review = Review(
    subject=Subject(type="patch", provider="github-pr", provider_ref="123"),
    activities=[
        Comment(
            category="issue",
            author=Author(name="Jane"),
            content="Potential bug here",
            file="src/main.py",
            lines=[(42, 42)],
        )
    ]
)

# Save to file
dump(review, "output.yaml")
```

## CLI Tools

Install with CLI tools:

```bash
uv add opencodereview[tools]
```

### Viewing Reviews

List issues from review files:

```bash
reviews list .reviews                    # List all issues
reviews list .reviews --filter open      # Only open issues
reviews list .reviews --full             # Include full content
```

Show individual review details:

```bash
reviews show file.yaml                   # Summary view
reviews show file.yaml --full            # All activities
reviews show file.yaml --id C1           # Single issue thread
```

### Adding Activities

Add new activities interactively:

```bash
reviews add file.yaml                    # New activity (guided prompts)
reviews add file.yaml C1                 # Resolve/respond to existing activity
reviews add newfile.yaml                 # Creates new review file
```

## License

MIT
