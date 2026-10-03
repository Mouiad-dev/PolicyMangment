import re

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name: str) -> str:
    """CamelCase -> snake_case: UserAccount -> user_account."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()
