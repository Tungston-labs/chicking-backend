def serialize_category(name: str, count: int) -> dict[str, int | str]:
    return {
        "name": name,
        "count": count,
    }
