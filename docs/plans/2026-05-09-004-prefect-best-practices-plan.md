# Prefect Best Practices: Issues and Resolution Plan

## Current Issues

### I1: Ephemeral Server Per Invocation
Each `uv run binance-datatool gap-fill ...` or `sink ...` starts a temporary
Prefect server, runs the flow, then stops it. This adds ~3s overhead per
command and prevents flow run history from being persisted.

**Fix**: Use `prefect flow serve` for long-running flow service:
```bash
# Serve the historical pipeline directly (no server/worker needed)
uv run prefect flow serve src/binance_datatool/workflow/prefect_flows.py:historical_pipeline

# In another terminal, trigger runs
uv run prefect deployment run 'Historical Data Pipeline/historical_pipeline'
```
The `prefect flow serve` command runs flows without requiring a separate
server + worker infrastructure. It's ideal for local/CI development.

### I2: Flows Block on Sync CLI
CLI commands call `@flow` functions synchronously. Prefect 3.x flows
work best as async or with `.serve()` for persistent deployment.

**Fix**: Add deployment entry points that keep flows alive:
```python
if __name__ == "__main__":
    historical_pipeline.serve(name="daily-backfill", cron="0 6 * * *")
```

### I3: No Flow Deployment or Scheduling
`historical_pipeline` runs on-demand only. For production DataOps,
daily/weekly backfills should be scheduled.

**Fix**: Add deployment configuration:
```bash
prefect deploy src/binance_datatool/workflow/prefect_flows.py:daily_backfill \
  --name daily-backfill --cron "0 6 * * *"
```

### I4: No Health Check Flow Wrapper
`health check` runs as a standalone CLI command, not as a Prefect flow.
Health monitoring should be part of the scheduled pipeline.

**Fix**: Add `health_flow` to prefect_flows.py that wraps
`HealthCheckWorkflow` and `check_ducklake_anomalies`.

## Resolution Plan

| Issue | Effort | Priority | Action |
|-------|--------|----------|--------|
| I1 | 5 min | Medium | Add `prefect server start` to setup docs |
| I2 | 30 min | Low | Add `serve()` entry to prefect_flows.py |
| I3 | 15 min | Low | Add deployment config |
| I4 | 30 min | Low | Add health_flow() wrapper |
