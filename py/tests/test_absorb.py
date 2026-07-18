"""Security and directory-scan tests for the absorb importers."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from hebbianvault_mcp.absorb import cli, importers
from hebbianvault_mcp.absorb.importers import is_supported_store, scan_directory
from hebbianvault_mcp.absorb.secrets import redact_secrets, should_skip_file
from hebbianvault_mcp.config import HebbianConfig

BODY = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF"


def fixture(prefix: str) -> str:
    """Assemble an obviously fake token only at test runtime."""
    return f"{prefix}{BODY}"


class TestShouldSkipFile:
    def test_skips_env_and_credential_named_files(self) -> None:
        for name in [
            ".env",
            ".env.local",
            ".env.production",
            "credentials.json",
            "aws-credentials",
            "my-secret.md",
            "secrets.yaml",
            "token.txt",
            "api-tokens.json",
            "auth_token.md",
            "server.pem",
            "tls.key",
            "id_rsa",
            "identity.p12",
            "client.pfx",
        ]:
            assert should_skip_file(name)

    def test_keeps_ordinary_markdown_files(self) -> None:
        for name in ["MEMORY.md", "CLAUDE.md", "notes.md", "readme.md", "tokenizer.md"]:
            assert not should_skip_file(name)


class TestRedactSecrets:
    def test_redacts_token_shaped_strings(self) -> None:
        cases = [
            fixture("sk-"),
            fixture("sk-ant-api03-"),
            fixture("gh" + "p_"),
            fixture("github" + "_pat_11"),
            fixture("xox" + "b-"),
            "AKIA" + "IOSFODNN7EXAMPLE",
            fixture("AIza"),
            ".".join(["eyJ" + "hbGciOiJIUzI1NiI", "eyJ" + "zdWIiOiIxMjM0NTY", "SflKxwRJSMeKKF2QT4fwp"]),
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef0123",
        ]
        for secret in cases:
            result = redact_secrets(f"token is {secret} ok")
            assert secret not in result.content
            assert "[REDACTED]" in result.content
            assert result.redacted_count >= 1

    def test_short_hebbian_prefixed_values_are_not_redacted(self) -> None:
        # Keep the fake hbn_ fixture below the production regex's 16-char minimum.
        secret = "hbn_" + "fakefixture1234"
        result = redact_secrets(f"token is {secret} ok")
        assert result.content == f"token is {secret} ok"
        assert result.redacted_count == 0

    def test_redacts_tokens_adjacent_to_unicode_letters(self) -> None:
        cases = [
            fixture("sk-"),
            fixture("hbn_"),
            "deadbeef" * 5,
        ]
        for secret in cases:
            for content in [f"é{secret}", f"{secret}é"]:
                result = redact_secrets(content)
                assert secret not in result.content
                assert result.redacted_count > 0

    def test_keeps_bearer_word_but_redacts_value(self) -> None:
        result = redact_secrets("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456")
        assert "Bearer [REDACTED]" in result.content

    def test_redacts_url_embedded_credentials_and_keeps_context(self) -> None:
        cases = [
            (
                "db is postgresql://app.user:S3cretPassw0rd@db.example.com:6543/postgres ok",
                "postgresql://app.user:[REDACTED]@db.example.com:6543/postgres",
                "S3cretPassw0rd",
            ),
            (
                "cache at redis://:s3cretpass@localhost:6379/0",
                "redis://:[REDACTED]@localhost:6379/0",
                "s3cretpass",
            ),
            (
                "queue amqp://guest:guestpw@mq.internal:5672",
                "amqp://guest:[REDACTED]@mq.internal:5672",
                "guestpw",
            ),
        ]
        for input_text, keep, gone in cases:
            result = redact_secrets(input_text)
            assert keep in result.content
            assert gone not in result.content
            assert result.redacted_count >= 1

    def test_leaves_credential_free_urls_and_clean_prose_untouched(self) -> None:
        for text in [
            "see https://docs.example.com/path?q=1 for details",
            "git remote is ssh://git@github.com/org/repo.git",
            "local dev on http://localhost:3000/app",
            "This is a normal memory note about the Q2 roadmap and pricing.",
        ]:
            result = redact_secrets(text)
            assert result.content == text
            assert result.redacted_count == 0

    def test_redacts_supabase_key_prefixes(self) -> None:
        for secret in [fixture("sb_secret_"), fixture("sbp_")]:
            result = redact_secrets(f"key is {secret} ok")
            assert secret not in result.content
            assert result.redacted_count >= 1


class TestImporters:
    def test_supported_stores(self) -> None:
        assert is_supported_store("claude-code")
        assert is_supported_store("markdown")
        assert not is_supported_store("cursor")

    def test_scan_directory_excludes_and_redacts_files(self, tmp_path: Path) -> None:
        (tmp_path / "MEMORY.md").write_text("# Memory index\n\nThe index of everything.\n")
        (tmp_path / "CLAUDE.md").write_text("# Project rules\n\nUse Python.\n")
        gh_token = "gh" + "p_" + BODY
        sk_token = "sk-" + BODY
        nested = tmp_path / "sub"
        nested.mkdir()
        (nested / "creds-in-body.md").write_text(f"# Has a key\n\nmy token: {gh_token} here\n")
        (tmp_path / ".env").write_text(f"SECRET={gh_token}\n")
        (tmp_path / "api-credentials.md").write_text(f"# creds\n\n{sk_token}\n")
        package = tmp_path / "node_modules" / "pkg"
        package.mkdir(parents=True)
        (package / "README.md").write_text("# dep\n")
        (tmp_path / "data.json").write_text("{}")

        result = scan_directory(tmp_path, "claude-code")

        assert [item.source_id for item in result.items] == [
            "CLAUDE.md",
            "MEMORY.md",
            "sub/creds-in-body.md",
        ]
        assert result.skipped_secret_files == ["api-credentials.md"]
        item = next(item for item in result.items if item.source_id == "sub/creds-in-body.md")
        assert gh_token not in item.content
        assert "[REDACTED]" in item.content
        assert result.redacted_secrets >= 1
        assert result.redacted_items >= 1

    def test_scan_directory_derives_title_and_stamps_metadata(self, tmp_path: Path) -> None:
        (tmp_path / "MEMORY.md").write_text("# Memory index\n\nThe index of everything.\n")

        result = scan_directory(tmp_path, "markdown")

        item = result.items[0]
        assert item.title == "Memory index"
        assert item.store_kind == "markdown"
        assert item.updated_at.endswith("Z")

    def test_scan_directory_omits_created_at_without_birthtime(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        (tmp_path / "MEMORY.md").write_text("# Memory index\n")
        monkeypatch.setattr(importers, "_birthtime_iso", lambda _stat: None)

        result = scan_directory(tmp_path, "markdown")

        assert result.items[0].created_at is None
        assert "created_at" not in result.items[0].as_dict()


async def test_absorb_batches_at_200_and_posts_existing_client_payload(
    tmp_path: Path, monkeypatch: Any
) -> None:
    for index in range(201):
        (tmp_path / f"note-{index:03}.md").write_text(f"# Note {index}\n")

    clients: list[Any] = []

    class FakeClient:
        def __init__(
            self, api_url: str, token: str, tenant: str | None, graph_pagination: bool
        ) -> None:
            self.posts: list[tuple[str, dict[str, Any]]] = []
            clients.append(self)

        async def post(self, path: str, body: dict[str, Any]) -> dict[str, int]:
            self.posts.append((path, body))
            return {"accepted": len(body["items"]), "duplicates": 0, "errors": 0}

    monkeypatch.setattr(cli, "HebbianClient", FakeClient)
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: HebbianConfig(api_url="https://api.example.test", token="fake-token"),
    )
    stderr = StringIO()

    exit_code = await cli.run_absorb(
        ["markdown", str(tmp_path), "--agent", "fake-agent"], stderr=stderr
    )

    assert exit_code == 0
    assert len(clients) == 1
    assert [len(body["items"]) for _, body in clients[0].posts] == [200, 1]
    assert [path for path, _ in clients[0].posts] == [
        "/v1/agents/fake-agent/absorb",
        "/v1/agents/fake-agent/absorb",
    ]
