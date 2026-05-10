# binance_datatool.cli

Typer CLI application. The entry point is `binance_datatool.cli:app`, exposed as the `binance-datatool`
console script via `pyproject.toml`.

## App Structure

```
binance-datatool [-v | -vv] [--archive-home PATH]   # Root Typer app with shared options
├── list-symbols                     # List symbols from remote archive
├── list-files                       # List archive files for symbols
├── download                         # Download archive files (aria2)
├── verify                           # Verify SHA256 checksums
├── gap-fill                         # Detect and fill gaps via REST API
├── health                           # Check data completeness and quality
├── sink                             # Transform Bronze→Silver→DuckDB
└── refresh-metadata                 # Refresh venue/symbol metadata tables
```

## Root Callback

The root `binance-datatool` app defines a callback that runs before any sub-command:

| Flag | Effect |
|------|--------|
| *(default)* | `loguru` level `WARNING`, unified `date \| level \| module - message` format |
| `-v` | `loguru` level `INFO`, same unified format |
| `-vv` | `loguru` level `DEBUG`, same unified format |
| `--archive-home` | Override the archive data directory. Stored in `ctx.obj["archive_home_override"]` and consumed by commands that need local archive storage (`download`, `verify`). See [`common.path`](../common/path.md) for resolution priority. |

`-v` is `count`-based — pass `-v -v` or `-vv` for DEBUG. All CLI logging is written
to `stderr` via `configure_cli_logging()` from [`common.logging`](../common/logging.md),
so sub-command stdout remains safe to pipe.

## Root Commands

| Command Set | Description | Reference |
|-------------|-------------|-----------|
| Root data commands | S3 archive listing, download, verify, gap-fill, health, sink, and metadata commands | [command reference](archive.md) |

---

See also: [Architecture](../../architecture.md) |
[Extending the Project — Adding a New CLI Command](../../extending.md#adding-a-new-cli-command)
