#!/usr/bin/env python3
"""
Validate commit messages according to Conventional Commits specification.
This script replaces the JavaScript commitlint tool with a Python implementation.
"""

import sys
import re
from typing import List, Tuple, Optional


def validate_commit_message(commit_msg_file: str) -> Tuple[bool, List[str]]:
    """
    Validate a commit message against Conventional Commits rules.

    Args:
        commit_msg_file: Path to the file containing the commit message

    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        with open(commit_msg_file, 'r') as f:
            commit_msg = f.read()
    except Exception as e:
        return False, [f"Failed to read commit message file: {e}"]

    # Remove comments (lines starting with #)
    commit_msg = '\n'.join([line for line in commit_msg.split('\n')
                           if not line.strip().startswith('#')])

    # Split into header, body, and footer
    parts = commit_msg.split('\n\n', 2)
    header = parts[0].strip()
    body = parts[1].strip() if len(parts) > 1 else ""
    footer = parts[2].strip() if len(parts) > 2 else ""

    errors = []

    # Validate header
    header_errors = validate_header(header)
    errors.extend(header_errors)

    # Validate body
    if body:
        body_errors = validate_body(body)
        errors.extend(body_errors)

    # Validate footer
    if footer:
        footer_errors = validate_footer(footer)
        errors.extend(footer_errors)

    return len(errors) == 0, errors


def validate_header(header: str) -> List[str]:
    """Validate the header of the commit message."""
    errors = []

    # Check header max length
    if len(header) > 100:
        errors.append("header-max-length: Header must not exceed 100 characters")

    # Parse header into type, scope, and subject
    match = re.match(r'^([a-z]+)(\(([^)]+)\))?: (.+)$', header)
    if not match:
        errors.append("header-format: Header must follow format: type(scope): subject")
        return errors

    type_, _, scope, subject = match.groups()

    # Validate type
    type_errors = validate_type(type_)
    errors.extend(type_errors)

    # Validate subject
    subject_errors = validate_subject(subject)
    errors.extend(subject_errors)

    return errors


def validate_type(type_: str) -> List[str]:
    """Validate the type part of the commit message."""
    errors = []

    # Check if type is empty
    if not type_:
        errors.append("type-empty: Type must not be empty")

    # Check if type is lowercase
    if type_ and type_ != type_.lower():
        errors.append("type-case: Type must be lowercase")

    # Check if type is one of the allowed values
    allowed_types = [
        'build', 'chore', 'ci', 'docs', 'feat', 'fix',
        'perf', 'refactor', 'revert', 'style', 'test'
    ]
    if type_ and type_ not in allowed_types:
        errors.append(f"type-enum: Type must be one of {', '.join(allowed_types)}")

    return errors


def validate_subject(subject: str) -> List[str]:
    """Validate the subject part of the commit message."""
    errors = []

    # Check if subject is empty
    if not subject:
        errors.append("subject-empty: Subject must not be empty")
        return errors

    # Check if subject ends with a period
    if subject.endswith('.'):
        errors.append("subject-full-stop: Subject must not end with a period")

    # Check subject case (should not be sentence-case, start-case, pascal-case, or upper-case)
    if subject[0].isupper() and not subject.isupper():  # Not sentence-case or start-case
        errors.append("subject-case: Subject must not be sentence-case or start-case")

    if subject.isupper():  # Not upper-case
        errors.append("subject-case: Subject must not be upper-case")

    # Check for pascal-case (each word starts with uppercase)
    words = subject.split()
    if all(word[0].isupper() for word in words if word):
        errors.append("subject-case: Subject must not be pascal-case")

    return errors


def validate_body(body: str) -> List[str]:
    """Validate the body of the commit message."""
    errors = []

    # Check body max line length
    for line in body.split('\n'):
        if len(line) > 100:
            errors.append("body-max-line-length: Body lines must not exceed 100 characters")
            break

    return errors


def validate_footer(footer: str) -> List[str]:
    """Validate the footer of the commit message."""
    errors = []

    # Check footer max line length
    for line in footer.split('\n'):
        if len(line) > 100:
            errors.append("footer-max-line-length: Footer lines must not exceed 100 characters")
            break

    return errors


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 2:
        print("Error: Please provide the commit message file as an argument")
        sys.exit(1)

    commit_msg_file = sys.argv[1]
    is_valid, errors = validate_commit_message(commit_msg_file)

    if not is_valid:
        print("Commit message validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("Commit message validation passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
