"""Tests for log sanitizer utility."""

from pysmarthashtag.api.log_sanitizer import (
    get_data_summary,
    sanitize_log_data,
)


class TestSanitizeLogData:
    """Test cases for sanitize_log_data function."""

    def test_sanitize_vin(self):
        """Test VIN is masked in dictionary."""
        data = {"vin": "W1T12345678901234", "model": "Smart #1"}
        result = sanitize_log_data(data)
        assert result["model"] == "Smart #1"
        assert result["vin"] == "***1234"

    def test_sanitize_access_token(self):
        """Test access token is masked."""
        data = {"access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["status"] == "ok"
        assert "eyJ" not in result["access_token"]
        assert result["access_token"].startswith("***")

    def test_sanitize_refresh_token(self):
        """Test refresh token is masked."""
        data = {"refresh_token": "some_refresh_token_value", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["refresh_token"].startswith("***")

    def test_sanitize_username(self):
        """Test username is masked."""
        data = {"username": "user@example.com", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["username"] == "***.com"
        assert "user@" not in result["username"]

    def test_sanitize_user_id(self):
        """Test user ID is masked."""
        data = {"userId": "112233445566", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["userId"] == "***5566"

    def test_sanitize_session_token(self):
        """Test session token is masked."""
        data = {"sessionToken": "abc123def456", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["sessionToken"].startswith("***")

    def test_sanitize_authorization_header(self):
        """Test authorization header is masked."""
        data = {"authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature"}
        result = sanitize_log_data(data)
        assert result["authorization"].startswith("***")

    def test_sanitize_nested_dict(self):
        """Test nested dictionaries are sanitized."""
        data = {
            "data": {
                "vin": "W1T12345678901234",
                "details": {"access_token": "secret_token_value"},
            },
            "status": "ok",
        }
        result = sanitize_log_data(data)
        assert result["data"]["vin"].startswith("***")
        assert result["data"]["details"]["access_token"].startswith("***")
        assert result["status"] == "ok"

    def test_sanitize_list_of_dicts(self):
        """Test list of dictionaries are sanitized."""
        data = [{"vin": "W1T12345678901234"}, {"vin": "W1T98765432101234"}]
        result = sanitize_log_data(data)
        assert result[0]["vin"].startswith("***")
        assert result[1]["vin"].startswith("***")

    def test_sanitize_string_with_vin(self):
        """Test VIN is masked in string."""
        text = "Processing vehicle W1T12345678901234 status"
        result = sanitize_log_data(text)
        assert "W1T12345678901234" not in result
        assert "***" in result

    def test_sanitize_string_with_bearer_token(self):
        """Test Bearer token is masked in string."""
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload"
        result = sanitize_log_data(text)
        assert "eyJhbGciOiJSUzI1NiJ9" not in result
        assert "Bearer ***" in result

    def test_sanitize_preserves_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        data = {
            "chargeLevel": 85,
            "status": "CHARGING",
            "temperature": 22.5,
            "isConnected": True,
        }
        result = sanitize_log_data(data)
        assert result == data

    def test_sanitize_empty_values(self):
        """Test empty values are handled correctly."""
        data = {"vin": "", "access_token": None, "status": "ok"}
        result = sanitize_log_data(data)
        assert result["vin"] == ""
        assert result["access_token"] is None
        assert result["status"] == "ok"

    def test_sanitize_device_id(self):
        """Test device ID is masked."""
        data = {"device_id": "abc123456789", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["device_id"].startswith("***")

    def test_sanitize_api_access_token(self):
        """Test API access token is masked."""
        data = {"apiAccessToken": "my_api_access_token", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["apiAccessToken"].startswith("***")

    def test_sanitize_api_user_id(self):
        """Test API user ID is masked."""
        data = {"apiUserId": "112233445566", "status": "ok"}
        result = sanitize_log_data(data)
        assert result["apiUserId"].startswith("***")

    def test_max_depth_protection(self):
        """Test max depth protection prevents infinite recursion."""
        # Create deeply nested structure
        data = {"level": 0}
        current = data
        for i in range(15):
            current["nested"] = {"level": i + 1}
            current = current["nested"]
        current["vin"] = "W1T12345678901234"

        result = sanitize_log_data(data)
        assert result is not None

        # Verify depth truncation occurs since nesting exceeds max_depth (10)
        nested = result
        depth = 0
        while "nested" in nested and depth < 15:
            nested = nested["nested"]
            depth += 1
        # Should have truncated before depth 15
        assert depth <= 11  # max_depth (10) + 1 for truncation marker
        # Check that truncation marker appears or depth was limited
        if depth >= 10:
            assert "..." in nested or nested == {"...": "max depth reached"}


class TestGetDataSummary:
    """Test cases for get_data_summary function."""

    def test_summary_basic(self):
        """Test basic data summary."""
        data = {"chargeLevel": 85, "status": "CHARGING", "temperature": 22.5}
        result = get_data_summary(data)
        assert "chargeLevel=85" in result
        assert "status=CHARGING" in result

    def test_summary_excludes_sensitive_fields(self):
        """Test summary excludes sensitive fields."""
        data = {"vin": "W1T12345678901234", "chargeLevel": 85, "access_token": "secret"}
        result = get_data_summary(data)
        assert "vin=" not in result
        assert "access_token=" not in result
        assert "chargeLevel=85" in result

    def test_summary_excludes_nested_objects(self):
        """Test summary excludes nested objects."""
        data = {"chargeLevel": 85, "nested": {"value": 123}, "list_data": [1, 2, 3]}
        result = get_data_summary(data)
        assert "nested=" not in result
        assert "list_data=" not in result

    def test_summary_with_specific_keys(self):
        """Test summary with specific keys."""
        data = {"chargeLevel": 85, "status": "CHARGING", "temperature": 22.5}
        result = get_data_summary(data, include_keys=["chargeLevel"])
        assert "chargeLevel=85" in result
        assert "status=" not in result

    def test_summary_empty_dict(self):
        """Test summary of empty dictionary."""
        result = get_data_summary({})
        assert "<dict with 0 keys>" == result

    def test_summary_non_dict(self):
        """Test summary of non-dictionary."""
        result = get_data_summary([1, 2, 3])
        assert "<list>" == result

    def test_summary_limits_items(self):
        """Test summary limits number of items."""
        data = {f"key{i}": i for i in range(10)}
        result = get_data_summary(data)
        # Should only include up to 5 items
        assert result.count("=") <= 5
