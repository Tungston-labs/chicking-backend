from typing import Iterable


BLOG_CATEGORIES = [
    "New Store Openings",
    "Training & Support",
    "Menu Innovations",
    "Franchise Opportunities",
    "Upcoming Locations",
]

READ_TIME_OPTIONS = [
    "2 min Read",
    "3 min Read",
    "4 min Read",
    "5 min Read",
    "8 min Read",
    "10+ min Read",
]

DEFAULT_BLOG_TITLE = "Untitled Blog Post"
DEFAULT_BLOG_CATEGORY = BLOG_CATEGORIES[0]
DEFAULT_AUTHOR = "Robert Pattinson"
DEFAULT_AUTHOR_ROLE = "Super Admin"
DEFAULT_BLOG_STATUS = "Draft"
DEFAULT_READ_TIME = READ_TIME_OPTIONS[0]


def normalize_category(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return DEFAULT_BLOG_CATEGORY

    for category in BLOG_CATEGORIES:
        if category.lower() == normalized.lower():
            return category

    return normalized


def normalize_read_time(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return DEFAULT_READ_TIME

    for option in READ_TIME_OPTIONS:
        if option.lower() == normalized.lower():
            return option

    return normalized


def normalize_text_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "\n\n".join(parts)

    return str(value or "").strip()


def build_excerpt(blog: dict[str, object], max_length: int = 160) -> str:
    excerpt = str(blog.get("excerpt") or "").strip()
    if excerpt:
        return excerpt

    content = " ".join(normalize_text_content(blog.get("content")).split()).strip()
    if content:
        if len(content) <= max_length:
            return content
        return f"{content[: max_length - 3].rstrip()}..."

    title = str(blog.get("title") or "").strip()
    return title or DEFAULT_BLOG_TITLE
