"""Pulse (Sprint) assignment utilities for Jira issues."""

import logging
from datetime import datetime
from typing import Optional

from jira import JIRA

logger = logging.getLogger("sync-bot-server")


def calculate_pulse(closed_date: str, reference_start_date: str = "2026-01-05") -> tuple[int, int]:
    """Calculate pulse number based on closed date.

    Pulses follow a strict 2-week (14-day) cadence starting from a reference date.
    There are 26 pulses per year, and the count resets every year.

    Args:
        closed_date: Date when issue was closed (ISO format: YYYY-MM-DD)
        reference_start_date: Start date of Pulse 1 for the reference year (default: Jan 5, 2026)

    Returns:
        tuple: (year, pulse_number) where pulse_number is 1-26

    Examples:
        >>> calculate_pulse("2026-01-05", "2026-01-05")
        (2026, 1)
        >>> calculate_pulse("2026-01-19", "2026-01-05")
        (2026, 2)
        >>> calculate_pulse("2026-02-11", "2026-01-05")
        (2026, 3)
    """
    # Parse dates
    closed = datetime.strptime(closed_date, "%Y-%m-%d")
    reference = datetime.strptime(reference_start_date, "%Y-%m-%d")

    # Calculate days since reference
    days_diff = (closed - reference).days

    # Each pulse is 14 days
    pulse_offset = days_diff // 14

    # Calculate pulse number (1-indexed, wraps every 26 pulses)
    pulse_number = (pulse_offset % 26) + 1

    # Calculate year (reference year + full cycles of 26 pulses)
    year = reference.year + (pulse_offset // 26)

    return (year, pulse_number)


def format_sprint_name(
    year: int, pulse_number: int, pattern: str = "Pulse {year}#{number} - Web & Design"
) -> str:
    """Format sprint name according to the configured pattern.

    Args:
        year: Year of the pulse
        pulse_number: Pulse number (1-26)
        pattern: Name pattern with {year} and {number} placeholders

    Returns:
        str: Formatted sprint name

    Examples:
        >>> format_sprint_name(2026, 3)
        'Pulse 2026#03 - Web & Design'
        >>> format_sprint_name(2026, 24)
        'Pulse 2026#24 - Web & Design'
    """
    # Format pulse number with leading zero (01-26)
    return pattern.format(year=year, number=f"{pulse_number:02d}")


def find_sprint_start_date(jira: JIRA, board_id: int, sprint_name: str) -> Optional[str]:
    """Find a sprint start date by its name on a specific board.

    Returns the date portion (YYYY-MM-DD) when startDate is available.
    """
    try:
        start_at = 0
        max_results = 50

        while True:
            sprints = jira._get_json(
                f"agile/1.0/board/{board_id}/sprint",
                params={"startAt": start_at, "maxResults": max_results},
            )

            for sprint in sprints.get("values", []):
                if sprint.get("name") == sprint_name:
                    start_date = sprint.get("startDate")
                    if start_date:
                        return start_date.split("T")[0]
                    logger.warning(
                        f"Sprint '{sprint_name}' has no startDate; using configured fallback"
                    )
                    return None

            if sprints.get("isLast", True):
                break

            start_at += max_results

        logger.warning(f"Sprint '{sprint_name}' not found on board {board_id}")
        return None

    except Exception as e:
        logger.error(f"Error finding sprint '{sprint_name}' on board {board_id}: {e}")
        return None


def find_sprint_by_name(jira: JIRA, board_id: int, sprint_name: str) -> Optional[int]:
    """Find a sprint ID by its name on a specific board.

    Args:
        jira: Authenticated Jira client
        board_id: ID of the Jira board to search
        sprint_name: Name of the sprint to find

    Returns:
        Optional[int]: Sprint ID if found, None otherwise
    """
    try:
        # Get all sprints from the board
        # The API may paginate results, so we need to handle that
        start_at = 0
        max_results = 50

        while True:
            sprints = jira._get_json(
                f"agile/1.0/board/{board_id}/sprint",
                params={"startAt": start_at, "maxResults": max_results},
            )

            for sprint in sprints.get("values", []):
                if sprint.get("name") == sprint_name:
                    return sprint.get("id")

            # Check if there are more results
            if sprints.get("isLast", True):
                break

            start_at += max_results

        logger.warning(f"Sprint '{sprint_name}' not found on board {board_id}")
        return None

    except Exception as e:
        logger.error(f"Error finding sprint '{sprint_name}' on board {board_id}: {e}")
        return None


def assign_sprint_to_issue(
    jira: JIRA, issue_key: str, sprint_id: int, sprint_field_id: str
) -> bool:
    """Assign a sprint to a Jira issue.

    Args:
        jira: Authenticated Jira client
        issue_key: Key of the issue to update (e.g., "WD-12345")
        sprint_id: ID of the sprint to assign
        sprint_field_id: Custom field ID for sprint (e.g., "customfield_10020")

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        issue = jira.issue(issue_key)
        issue.update(fields={sprint_field_id: sprint_id})
        logger.info(f"Assigned sprint {sprint_id} to issue {issue_key}")
        return True
    except Exception as e:
        logger.error(f"Error assigning sprint {sprint_id} to issue {issue_key}: {e}")
        return False


def should_assign_pulse(jira_issue, pulse_config: dict, jira_project_key: str) -> tuple[bool, str]:
    """Check if pulse should be assigned to the issue based on pre-conditions.

    Args:
        jira_issue: Jira issue object
        pulse_config: Pulse assignment configuration from settings
        jira_project_key: Expected project key

    Returns:
        tuple: (should_assign: bool, reason: str)
    """
    # Check if feature is enabled
    if not pulse_config.get("enabled", False):
        return False, "Pulse assignment is not enabled"

    # Check if project matches
    if not pulse_config.get("project_key"):
        return False, "Pulse assignment project_key not configured"

    if jira_issue.fields.project.key != pulse_config["project_key"]:
        return (
            False,
            f"Issue project {jira_issue.fields.project.key} does not match "
            f"pulse_assignment.project_key {pulse_config['project_key']}",
        )

    # Check if issue already has a sprint assigned
    sprint_field_id = pulse_config.get("sprint_field_id", "customfield_10020")
    current_sprint = getattr(jira_issue.fields, sprint_field_id, None)
    if current_sprint is not None:
        return False, f"Issue already has sprint assigned: {current_sprint}"

    return True, "All conditions met"


def process_pulse_assignment(
    jira: JIRA,
    jira_issue,
    closed_date: str,
    pulse_config: dict,
    jira_project_key: str,
) -> Optional[str]:
    """Process pulse assignment for a closed issue.

    This is the main orchestration function that handles the complete pulse assignment workflow:
    1. Validates pre-conditions
    2. Calculates the appropriate pulse
    3. Looks up the sprint in Jira
    4. Assigns the sprint to the issue

    Args:
        jira: Authenticated Jira client
        jira_issue: Jira issue object to assign pulse to
        closed_date: Date when the GitHub issue was closed (ISO format)
        pulse_config: Pulse assignment configuration from settings
        jira_project_key: Jira project key

    Returns:
        Optional[str]: Success message if pulse was assigned, None otherwise
    """
    # Check pre-conditions
    should_assign, reason = should_assign_pulse(jira_issue, pulse_config, jira_project_key)
    if not should_assign:
        logger.info(f"Skipping pulse assignment for {jira_issue.key}: {reason}")
        return None

    # Get configuration
    board_id = pulse_config.get("board_id")
    sprint_field_id = pulse_config.get("sprint_field_id", "customfield_10020")
    sprint_name_pattern = pulse_config.get(
        "sprint_name_pattern", "Pulse {year}#{number} - Web & Design"
    )
    if not board_id:
        logger.error("Pulse assignment board_id not configured")
        return None

    year = int(closed_date.split("-")[0])
    pulse_one_name = format_sprint_name(year, 1, sprint_name_pattern)
    reference_date = find_sprint_start_date(jira, board_id, pulse_one_name)
    if not reference_date:
        logger.warning(
            "Pulse 01 startDate is unavailable. Skipping pulse assignment until it exists."
        )
        return None

    try:
        # Calculate pulse
        year, pulse_number = calculate_pulse(closed_date, reference_date)
        sprint_name = format_sprint_name(year, pulse_number, sprint_name_pattern)

        logger.info(
            f"Calculated pulse for {jira_issue.key}: {sprint_name} " f"(closed on {closed_date})"
        )

        # Find sprint
        sprint_id = find_sprint_by_name(jira, board_id, sprint_name)
        if sprint_id is None:
            logger.warning(
                f"Sprint '{sprint_name}' not found on board {board_id}. "
                f"Skipping pulse assignment for {jira_issue.key}"
            )
            return None

        # Assign sprint
        success = assign_sprint_to_issue(jira, jira_issue.key, sprint_id, sprint_field_id)
        if success:
            return f"Assigned pulse {sprint_name} to {jira_issue.key}"
        else:
            return None

    except Exception as e:
        logger.error(f"Error processing pulse assignment for {jira_issue.key}: {e}")
        return None
