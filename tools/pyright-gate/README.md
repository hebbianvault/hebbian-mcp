# pyright-gate (vendored)

`pyright-gate` here is a byte-for-byte copy of shared-platform `tools/pyright-gate/pyright-gate`
(hebbianvault/shared-platform#800, gate PR #2163, copied at a4aa0fdf114f2f752d8f27eddd6d7e135e6a598c).
It is vendored because CI here cannot read the private shared-platform repo.

- CI: `python3 tools/pyright-gate/pyright-gate check --root .` fails on any (file, rule) error count
  above `pyright-baseline.json` (rc 1), and on any failure to run (rc 2).
- After burning down errors: `tools/pyright-gate/pyright-gate baseline --root .` and commit the new baseline.
- The shared pre-push hook (arm F) runs its own copy against the same `pyrightconfig.json` and baseline.
