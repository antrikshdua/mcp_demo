"""SQL query safety validation — blocks dangerous operations, strips comments."""

from __future__ import annotations

import re


def _has_multiple_statements_outside_quotes(sql: str) -> bool:
    """Return True if sql contains more than one statement (semicolon outside quotes).

    Allows a single trailing semicolon but rejects anything after it.
    Handles single quotes (with '' escaping), double quotes, and backticks.
    """
    in_single = False
    in_double = False
    in_backtick = False
    semicolon_count = 0
    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]
        if ch == "'" and not in_double and not in_backtick:
            # Handle doubled single-quote escape: ''
            if i + 1 < length and sql[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif ch == ";" and not in_single and not in_double and not in_backtick:
            semicolon_count += 1
        i += 1

    if semicolon_count == 0:
        return False
    if semicolon_count >= 2:
        return True

    # Exactly one semicolon — allowed only if it is a trailing one
    last_index = sql.rfind(";")
    return bool(sql[last_index + 1:].strip())


# Keywords that must not appear in a read-only query
_DANGEROUS_KEYWORDS = [
    # Data modification
    "DELETE", "UPDATE", "INSERT", "MERGE", "TRUNCATE",
    # Schema modification
    "DROP", "CREATE", "ALTER",
    # Permissions
    "GRANT", "REVOKE",
    # Execution
    "EXEC", "EXECUTE", "CALL",
    # Data exfiltration
    "EXPORT",
]

_ALLOWED_START_PATTERNS = [
    r"^\s*SELECT\b",
    r"^\s*WITH\b",
]


def is_query_safe(query: str) -> tuple[bool, str]:
    """Validate that a SQL query is safe (read-only SELECT / WITH).

    Steps:
      1. Reject empty / whitespace-only queries.
      2. Strip SQL line comments (--) and block comments (/* */).
      3. Reject queries that do not start with SELECT or WITH.
      4. Reject multi-statement queries (more than one statement separated by ;).
      5. Reject queries containing dangerous DML/DDL keywords.

    Returns:
        (True, "")           — query is safe to execute
        (False, <reason>)    — query is not safe; reason describes the violation
    """
    if not query or not query.strip():
        return False, "Empty query is not allowed."

    sanitised = query.upper().strip()

    # Strip comments before any other validation
    sanitised = re.sub(r"--.*", "", sanitised)
    sanitised = re.sub(r"/\*.*?\*/", "", sanitised, flags=re.DOTALL)
    sanitised = sanitised.strip()

    if not sanitised:
        return False, "Query contains only comments with no actual SQL statement."

    # Must start with SELECT or WITH (CTEs)
    if not any(re.match(pat, sanitised) for pat in _ALLOWED_START_PATTERNS):
        first_word = sanitised.split()[0] if sanitised.split() else "unknown"
        return False, (
            f"Only SELECT and WITH queries are allowed. Query starts with: {first_word}"
        )

    # Reject multi-statement scripts
    if _has_multiple_statements_outside_quotes(sanitised):
        return False, (
            "Multiple SQL statements are not allowed. "
            "Execute one SELECT or WITH query at a time."
        )

    # Reject dangerous keywords at word boundaries
    for keyword in _DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sanitised):
            return False, (
                f"Query contains dangerous keyword '{keyword}'. "
                "Only read-only SELECT and WITH queries are allowed."
            )

    return True, ""
