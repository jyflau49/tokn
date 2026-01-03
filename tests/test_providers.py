"""Tests for provider plugins."""


from tokn.providers.base import RotationResult
from tokn.providers.github import GitHubProvider
from tokn.providers.terraform import TerraformAccountProvider, TerraformOrgProvider


class TestGitHubProvider:
    def test_does_not_support_auto_rotation(self):
        """GitHub PATs cannot be auto-rotated without OAuth App."""
        provider = GitHubProvider()
        assert provider.supports_auto_rotation is False

    def test_provides_manual_instructions(self):
        """Verify manual instructions are provided."""
        provider = GitHubProvider()
        instructions = provider.get_manual_instructions()

        assert "github.com/settings/tokens" in instructions
        assert "doppler secrets set" in instructions


class TestTerraformAccountProvider:
    def test_does_not_support_auto_rotation(self):
        """Terraform account tokens require OAuth flow."""
        provider = TerraformAccountProvider()
        assert provider.supports_auto_rotation is False

    def test_rotate_returns_manual_error(self):
        """Verify rotate returns error with instructions."""
        provider = TerraformAccountProvider()
        result = provider.rotate("dummy_token")

        assert result.success is False
        assert "terraform login" in result.error

    def test_provides_manual_instructions(self):
        """Verify manual instructions mention terraform login."""
        provider = TerraformAccountProvider()
        instructions = provider.get_manual_instructions()

        assert "terraform login" in instructions
        assert "credentials.tfrc.json" in instructions


class TestTerraformOrgProvider:
    def test_supports_auto_rotation(self):
        """Terraform org tokens can be auto-rotated."""
        provider = TerraformOrgProvider()
        assert provider.supports_auto_rotation is True

    def test_rotate_requires_org_name(self):
        """Verify org_name is required for rotation."""
        provider = TerraformOrgProvider()
        result = provider.rotate("dummy_token")

        assert result.success is False
        assert "org_name required" in result.error


class TestRotationResult:
    def test_success_result(self):
        """Verify successful rotation result."""
        result = RotationResult(success=True, new_token="new_token_123")

        assert result.success is True
        assert result.new_token == "new_token_123"
        assert result.error is None

    def test_failure_result(self):
        """Verify failed rotation result."""
        result = RotationResult(success=False, error="API error")

        assert result.success is False
        assert result.new_token is None
        assert result.error == "API error"

    def test_result_has_timestamp(self):
        """Verify rotation result includes timestamp."""
        result = RotationResult(success=True, new_token="token")

        assert result.rotated_at is not None
