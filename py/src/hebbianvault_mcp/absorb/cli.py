"""The one-shot ``hebbian-mcp absorb`` context-store importer."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TextIO, TypeVar

from ..client import HebbianClient
from ..config import load_config
from .importers import is_supported_store, scan_directory, supported_stores

BATCH_SIZE = 200
T = TypeVar("T")

USAGE = "\n".join(
    [
        "Usage: hebbian-mcp absorb <store> <dir> --agent <agent_id> [--dry-run]",
        "",
        f"  store    one of: {', '.join(supported_stores())}",
        "  dir      path to the context store directory",
        "  --agent  the agent principal UUID to absorb into (the agent you already use)",
        "  --dry-run  walk and report; do not upload",
        "",
        "Auth: set HEBBIAN_API_TOKEN to the agent's token (or use the config file).",
        "Reads *.md files, skips credential-named files, redacts token-shaped strings,",
        "then uploads each file as a review-lane seed attributed to the agent.",
    ]
)


@dataclass(frozen=True)
class AbsorbArgs:
    """Validated CLI arguments."""

    store: str
    directory: str
    agent_id: str
    dry_run: bool


def _parse_flags(argv: Sequence[str]) -> tuple[str | None, bool, list[str]]:
    agent_id: str | None = None
    dry_run = False
    positionals: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"--agent", "--agent-id"}:
            index += 1
            agent_id = argv[index] if index < len(argv) else None
        elif arg.startswith("--agent="):
            agent_id = arg[len("--agent=") :]
        elif arg == "--dry-run":
            dry_run = True
        else:
            positionals.append(arg)
        index += 1
    return agent_id, dry_run, positionals


def _resolve_args(argv: Sequence[str], stderr: TextIO) -> AbsorbArgs | None:
    agent_id, dry_run, positionals = _parse_flags(argv)
    store, directory = (positionals + [None, None])[:2]
    if not store or not directory:
        print(USAGE, file=stderr)
        return None
    if not is_supported_store(store):
        print(
            f'absorb: unsupported store "{store}". Supported: {", ".join(supported_stores())}',
            file=stderr,
        )
        return None
    if not dry_run and not agent_id:
        print("absorb: --agent <agent_id> is required (or use --dry-run)", file=stderr)
        return None
    return AbsorbArgs(store=store, directory=directory, agent_id=agent_id or "", dry_run=dry_run)


def _chunks(items: Sequence[T], size: int) -> list[Sequence[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def run_absorb(argv: Sequence[str], stderr: TextIO | None = None) -> int:
    """Run absorb and return a shell-compatible exit code."""
    output: TextIO = sys.stderr if stderr is None else stderr
    args = _resolve_args(argv, output)
    if args is None:
        return 2

    scan = scan_directory(args.directory, args.store)
    print(
        f"[absorb] store={args.store} dir={args.directory}: {len(scan.items)} file(s) to absorb, "
        f"skipped {len(scan.skipped_secret_files)} credential-named file(s), "
        f"redacted {scan.redacted_secrets} token-shaped string(s) across "
        f"{scan.redacted_items} file(s)",
        file=output,
    )
    for filename in scan.skipped_secret_files:
        print(f"[absorb]   skipped (looks like secrets): {filename}", file=output)

    if not scan.items:
        print("[absorb] nothing to absorb.", file=output)
        return 0

    batches = _chunks(scan.items, BATCH_SIZE)
    if args.dry_run:
        agent_id = args.agent_id or "<agent_id>"
        print(
            f"[absorb] dry-run: would upload {len(scan.items)} item(s) to "
            f"/v1/agents/{agent_id}/absorb in {len(batches)} batch(es). No upload performed.",
            file=output,
        )
        return 0

    config = load_config()
    client = HebbianClient(config.api_url, config.token, config.tenant, config.graph_pagination)
    accepted = duplicates = errors = 0
    for index, batch in enumerate(batches, start=1):
        try:
            response: Any = await client.post(
                f"/v1/agents/{args.agent_id}/absorb",
                {"items": [item.as_dict() for item in batch]},
            )
            response = response if isinstance(response, dict) else {}
            batch_accepted = response.get("accepted", 0)
            batch_duplicates = response.get("duplicates", 0)
            batch_errors = response.get("errors", 0)
            accepted += batch_accepted if isinstance(batch_accepted, int) else 0
            duplicates += batch_duplicates if isinstance(batch_duplicates, int) else 0
            errors += batch_errors if isinstance(batch_errors, int) else 0
            print(
                f"[absorb] batch {index}/{len(batches)}: accepted {batch_accepted}, "
                f"duplicate {batch_duplicates}, error {batch_errors}",
                file=output,
            )
        except Exception as exc:  # noqa: BLE001 - command reports client failures cleanly
            print(f"[absorb] batch {index}/{len(batches)} failed: {exc}", file=output)
            return 1

    print(
        f"[absorb] done: {accepted} new seed(s), {duplicates} already absorbed, {errors} error(s). "
        "New seeds await review in the Hebbian review lane.",
        file=output,
    )
    return 1 if errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous console entry wrapper for the absorb subcommand."""
    return asyncio.run(run_absorb(argv if argv is not None else sys.argv[1:]))
