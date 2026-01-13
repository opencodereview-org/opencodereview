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

## License

MIT
