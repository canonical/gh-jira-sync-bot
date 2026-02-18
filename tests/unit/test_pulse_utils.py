"""Unit tests for pulse_utils module."""

from unittest.mock import Mock

from github_jira_sync_app.pulse_utils import calculate_pulse
from github_jira_sync_app.pulse_utils import format_sprint_name
from github_jira_sync_app.pulse_utils import process_pulse_assignment
from github_jira_sync_app.pulse_utils import should_assign_pulse


class TestCalculatePulse:
    """Test pulse calculation logic."""

    def test_pulse_3_mid_period(self):
        """Test that dates in the middle of a pulse round down correctly."""
        # Feb 11 is 37 days after Jan 5, which is 2 full periods + 9 days
        # Should be Pulse 3 (periods 0, 1, 2 = pulses 1, 2, 3)
        year, pulse = calculate_pulse("2026-02-11", "2026-01-05")
        assert year == 2026
        assert pulse == 3


class TestFormatSprintName:
    """Test sprint name formatting."""

    def test_default_pattern_single_digit(self):
        """Test default pattern with single digit pulse number."""
        name = format_sprint_name(2026, 1)
        assert name == "Pulse 2026#01 - Web & Design"


class TestShouldAssignPulse:
    """Test pre-condition validation logic."""

    def test_feature_disabled(self):
        """Test that disabled feature returns False."""
        pulse_config = {"enabled": False}
        mock_issue = Mock()

        should_assign, reason = should_assign_pulse(mock_issue, pulse_config, "WD")

        assert should_assign is False
        assert "not enabled" in reason

    def test_project_mismatch(self):
        """Test that project mismatch returns False."""
        pulse_config = {"enabled": True, "project_key": "WD"}
        mock_issue = Mock()
        mock_issue.fields.project.key = "OTHER"

        should_assign, reason = should_assign_pulse(mock_issue, pulse_config, "WD")

        assert should_assign is False
        assert "does not match" in reason

    def test_sprint_already_assigned(self):
        """Test that existing sprint returns False."""
        pulse_config = {
            "enabled": True,
            "project_key": "WD",
            "sprint_field_id": "customfield_10020",
        }
        mock_issue = Mock()
        mock_issue.fields.project.key = "WD"
        setattr(mock_issue.fields, "customfield_10020", 123)  # Sprint already assigned

        should_assign, reason = should_assign_pulse(mock_issue, pulse_config, "WD")

        assert should_assign is False
        assert "already has sprint" in reason


class TestProcessPulseAssignment:
    """Test the main pulse assignment workflow."""

    def test_process_pulse_assignment_success(self):
        """Test successful pulse assignment end-to-end."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.key = "WD-12345"
        mock_issue.fields.project.key = "WD"
        setattr(mock_issue.fields, "customfield_10020", None)

        # Mock sprint lookup + auto start date
        mock_jira._get_json.return_value = {
            "values": [
                {
                    "id": 101,
                    "name": "Pulse 2026#01 - Web & Design",
                    "startDate": "2026-01-05T09:00:00.000+0000",
                },
                {"id": 123, "name": "Pulse 2026#03 - Web & Design"},
            ],
            "isLast": True,
        }

        # Mock issue update
        mock_jira.issue.return_value = mock_issue

        pulse_config = {
            "enabled": True,
            "project_key": "WD",
            "board_id": 932,
            "sprint_field_id": "customfield_10020",
            "sprint_name_pattern": "Pulse {year}#{number} - Web & Design",
        }

        result = process_pulse_assignment(mock_jira, mock_issue, "2026-02-11", pulse_config, "WD")

        assert result is not None
        assert "Pulse 2026#03" in result
        assert "WD-12345" in result
        mock_issue.update.assert_called_once()

    def test_process_pulse_assignment_sprint_not_found(self):
        """Test that sprint not found returns None."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.key = "WD-12345"
        mock_issue.fields.project.key = "WD"
        setattr(mock_issue.fields, "customfield_10020", None)

        # Sprint not found
        mock_jira._get_json.return_value = {
            "values": [],
            "isLast": True,
        }

        pulse_config = {
            "enabled": True,
            "project_key": "WD",
            "board_id": 932,
            "sprint_field_id": "customfield_10020",
        }

        result = process_pulse_assignment(mock_jira, mock_issue, "2026-02-11", pulse_config, "WD")

        assert result is None

    def test_process_pulse_assignment_missing_board_id(self):
        """Test that missing board_id returns None."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.key = "WD-12345"
        mock_issue.fields.project.key = "WD"
        setattr(mock_issue.fields, "customfield_10020", None)

        pulse_config = {
            "enabled": True,
            "project_key": "WD",
            # board_id missing
        }

        result = process_pulse_assignment(mock_jira, mock_issue, "2026-02-11", pulse_config, "WD")

        assert result is None
