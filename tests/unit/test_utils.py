from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from github_jira_sync_app.main import _generate_summary
from github_jira_sync_app.main import merge_dicts
from github_jira_sync_app.main import truncate_description
from github_jira_sync_app.main import verify_signature


class TestMergeDicts:
    def test_merge_adds_missing_keys(self):
        d1 = {"a": 1}
        d2 = {"b": 2}
        merge_dicts(d1, d2)
        assert d1 == {"a": 1, "b": 2}

    def test_merge_does_not_override_existing(self):
        d1 = {"a": 1}
        d2 = {"a": 99}
        merge_dicts(d1, d2)
        assert d1 == {"a": 1}

    def test_merge_nested_dicts(self):
        d1 = {"settings": {"a": 1}}
        d2 = {"settings": {"a": 99, "b": 2}}
        merge_dicts(d1, d2)
        assert d1 == {"settings": {"a": 1, "b": 2}}

    def test_merge_deep_nested(self):
        d1 = {"l1": {"l2": {"l3_a": 1}}}
        d2 = {"l1": {"l2": {"l3_b": 2}}}
        merge_dicts(d1, d2)
        assert d1 == {"l1": {"l2": {"l3_a": 1, "l3_b": 2}}}

    def test_merge_empty_source(self):
        d1 = {"a": 1}
        merge_dicts(d1, {})
        assert d1 == {"a": 1}

    def test_merge_empty_target(self):
        d1 = {}
        merge_dicts(d1, {"a": 1})
        assert d1 == {"a": 1}


class TestTruncateDescription:
    def test_short_string_unchanged(self):
        s = "short text"
        assert truncate_description(s) == s

    def test_exactly_at_limit(self):
        s = "x" * 28000
        assert truncate_description(s) == s

    def test_over_limit_truncated(self):
        s = "x" * 30000
        result = truncate_description(s)
        assert result.startswith("x" * 28000 + "...")
        assert "Text exceeded Jira maximum length" in result
        assert len(result) < 30000


class TestGenerateSummary:
    def _make_issue(self, **kwargs):
        issue = MagicMock()
        issue.title = kwargs.get("title", "Test Issue Title")
        issue.user.login = kwargs.get("user_login", "test-user")
        issue.repository.name = kwargs.get("repo_name", "test-repo")
        return issue

    def test_default_falls_back_to_title(self):
        issue = self._make_issue()
        result = _generate_summary({}, issue)
        assert result == "Test Issue Title"

    def test_empty_summary_falls_back_to_title(self):
        issue = self._make_issue()
        result = _generate_summary({"summary": ""}, issue)
        assert result == "Test Issue Title"

    def test_custom_format_with_title(self):
        issue = self._make_issue()
        result = _generate_summary({"summary": "[{issue.repository.name}] {issue.title}"}, issue)
        assert result == "[test-repo] Test Issue Title"

    def test_custom_format_with_user(self):
        issue = self._make_issue()
        result = _generate_summary({"summary": "{issue.user.login}: {issue.title}"}, issue)
        assert result == "test-user: Test Issue Title"

    def test_invalid_format_falls_back_to_title(self):
        issue = self._make_issue()
        # Use a format string that will cause an exception (KeyError)
        result = _generate_summary({"summary": "{nonexistent_var}"}, issue)
        assert result == "Test Issue Title"

    def test_non_string_summary_falls_back_to_title(self):
        issue = self._make_issue()
        result = _generate_summary({"summary": 123}, issue)
        assert result == "Test Issue Title"


class TestVerifySignature:
    def _compute_signature(self, payload: bytes, secret: str) -> str:
        import hashlib
        import hmac as _hmac

        hash_obj = _hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
        return "sha256=" + hash_obj.hexdigest()

    def test_valid_signature_passes(self):
        payload = b'{"action": "opened"}'
        secret = "test-secret"
        sig = self._compute_signature(payload, secret)
        # Should not raise
        verify_signature(payload, secret, sig)

    def test_missing_header_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_signature(b"body", "secret", "")
        assert exc_info.value.status_code == 403
        assert "missing" in exc_info.value.detail.lower()

    def test_invalid_signature_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_signature(b"body", "secret", "sha256=invalid")
        assert exc_info.value.status_code == 403
        assert "didn't match" in exc_info.value.detail
