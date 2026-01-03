"""HCP Terraform token rotation providers."""

from tokn.providers.base import RotationResult, TokenProvider


class TerraformAccountProvider(TokenProvider):
    def __init__(self):
        super().__init__("HCP Terraform Account Token")

    @property
    def supports_auto_rotation(self) -> bool:
        return False

    def rotate(self, current_token: str, **kwargs) -> RotationResult:
        return RotationResult(
            success=False, error="Manual rotation required via 'terraform login'"
        )

    def get_manual_instructions(self) -> str:
        return """
Manual rotation required for HCP Terraform Account Token:

1. Run: terraform login
2. Follow OAuth flow in browser
3. Token will be saved to ~/.terraform.d/credentials.tfrc.json
"""
