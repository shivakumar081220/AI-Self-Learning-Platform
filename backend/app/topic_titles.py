import re


_GENERATED_TOPIC_SUFFIX = re.compile(r"\s+·\s+\d+-\d+$")


def display_topic_title(title: str) -> str:
    """Remove the legacy internal generation marker from generated topic titles."""
    return _GENERATED_TOPIC_SUFFIX.sub("", title)
