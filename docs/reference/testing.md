# Test Organization

```
tests/
├── conftest.py                 # Shared test support (FakeArchiveClient, sample_archive_files)
├── data/                       # Static test fixtures (e.g., sample data files)
├── test_archive_client.py      # Archive client unit and integration tests
├── test_archive_workflow.py    # Workflow unit and integration tests (list + download + verify)
├── test_checksum.py            # checksum module unit tests (calc, read, verify_single_file)
├── test_cli.py                 # CLI smoke tests (list-symbols, list-files, download, verify)
├── test_downloader.py          # aria2 downloader unit tests (proxy, batching, retry)
├── test_enums.py               # common.enums property tests
├── test_filter.py              # Symbol filter unit tests
├── test_path.py                # Archive-home resolution (override, env var, missing)
├── test_progress.py            # Progress-reporting framework (LogReporter, TqdmReporter)
├── test_symbol_dir.py          # SymbolArchiveDir, create_symbol_archive_dir, marker protocol
└── test_symbols.py             # Symbol inference unit and integration tests
```

## Conventions

- **Unit tests** use `monkeypatch` to replace HTTP methods with fake responses.
- **Integration tests** are marked with `@pytest.mark.integration` and skipped by default.
  Run them explicitly with `pytest --run-integration`.
- **CLI tests** use `typer.testing.CliRunner` and monkeypatch the workflow's `run()` method so
  they run without network access.

## Shared Test Support in `conftest.py`

- **`FakeArchiveClient`** — a programmable stub configured entirely via constructor
  kwargs (`symbols=`, `files_by_symbol=`, `errors_by_symbol=`). It implements
  `list_symbols`, `list_symbol_files`, and `list_symbol_files_batch`. The batch
  method records `progress_bar` state for assertion in tests. Prefer extending
  this stub over re-implementing per-test fakes when you add new workflows.
- **`sample_archive_files`** — a representative pair of `ArchiveFile` entries
  (`.zip` + `.zip.CHECKSUM`) for list-files-style workflow and CLI tests.
- **`--run-integration`** — a custom pytest option that unlocks the `integration`
  marker. The default run skips every integration test.

## Test-Driven Development (TDD) & Specs-Driven Development Guidance

This project follows a specs-driven development workflow. The goal is to keep
features small, well-specified, and covered by tests before implementation.

Workflows
- Every new workflow, adapter, or public behaviour MUST have:
  1. A short human-readable spec in `docs/specs-driven-development.md` describing
     inputs, outputs, success criteria, error modes, and side-effects.
  2. Unit tests that assert the behaviour at the workflow boundary using
     injected fakes (e.g. `FakeArchiveClient`).
  3. One or more integration tests (marked `@pytest.mark.integration`) that
     exercise I/O against a real endpoint or a recorded fixture.

Test templates
- Use the shared `FakeArchiveClient` fixture in `tests/conftest.py` for all
  adapter-driven workflow tests. If you need more control, extend the fake and
  add a focused fixture.

- Example unit test pattern for a new workflow:

```py
def test_my_workflow_happy_path(fake_archive_client, tmp_path):
    # Arrange: configure fake responses and inject dependencies
    fake_archive_client.configure(symbols=[...], files_by_symbol={...})
    workflow = MyWorkflow(client=fake_archive_client, archive_home=tmp_path)

    # Act
    result = asyncio.run(workflow.run())

    # Assert
    assert result.<expected> == <value>
```

Specs-driven PRs
- Every feature PR should include a one-paragraph spec summary and a link to
  (or an excerpt from) `docs/specs-driven-development.md` describing the change.
- Tests must be green locally before requesting review. Prefer small, focussed
  PRs that add one behaviour at a time.

Automation
- The default CI runs unit tests and linting. Integration tests are gated
  behind an environment variable or an explicit flag to avoid accidental
  external requests.

Subagents & Skills Guidance
- For agent-style automation, create small skill modules under `skills/` that
  call stable CLI commands or the public Python API. Each skill must have a
  spec describing the expected I/O and an accompanying unit test that mocks
  external side-effects.


---

See also: [Extending the Project](../extending.md) | [Architecture](../architecture.md)
