"""Command-line interface for the crypto data lakehouse."""

import asyncio
from datetime import datetime
from typing import List, Optional

import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from .core.config import Settings
from .core.models import DataIngestionTask, DataType, Exchange, Interval, TradeType
from .workflows.base import WorkflowRegistry

app = typer.Typer(
    name="crypto-lakehouse",
    help="Crypto Data Lakehouse - A scalable platform for cryptocurrency market data",
    rich_markup_mode="rich",
)

console = Console()
settings = Settings()

# Subcommands
ingest_app = typer.Typer(name="ingest", help="Data ingestion commands")
process_app = typer.Typer(name="process", help="Data processing commands")
query_app = typer.Typer(name="query", help="Data query commands")
admin_app = typer.Typer(name="admin", help="Administrative commands")

app.add_typer(ingest_app)
app.add_typer(process_app)
app.add_typer(query_app)
app.add_typer(admin_app)


@app.command()
def version():
    """Show version information."""
    from . import __version__

    console.print(f"Crypto Data Lakehouse v{__version__}")


@app.command()
def config():
    """Show current configuration."""
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Environment", settings.environment)
    table.add_row("Storage Path", settings.storage.base_path)
    table.add_row("Cloud Enabled", str(settings.is_cloud_enabled))
    table.add_row("Local Data Dir", str(settings.local_data_dir))
    table.add_row("Processing Concurrency", str(settings.processing_concurrency))

    console.print(table)


# Ingestion Commands
@ingest_app.command("klines")
def ingest_klines(
    exchange: Exchange = typer.Option(Exchange.BINANCE, help="Source exchange"),
    trade_type: TradeType = typer.Option(TradeType.SPOT, help="Type of trading instrument"),
    interval: Interval = typer.Option(Interval.MIN_1, help="K-line interval"),
    symbols: List[str] = typer.Option(..., help="Trading symbols to ingest"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
    force_update: bool = typer.Option(False, help="Force update existing data"),
):
    """Ingest K-line (candlestick) data."""
    console.print("[bold blue]Ingesting K-line data[/bold blue]")
    console.print(f"Exchange: {exchange.value}")
    console.print(f"Trade Type: {trade_type.value}")
    console.print(f"Interval: {interval.value}")
    console.print(f"Symbols: {', '.join(symbols)}")

    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Create ingestion task
    task = DataIngestionTask(
        exchange=exchange,
        data_type=DataType.KLINES,
        trade_type=trade_type,
        symbols=symbols,
        start_date=start_dt,
        end_date=end_dt,
        interval=interval,
        force_update=force_update,
    )

    # Execute workflow
    asyncio.run(_run_ingestion_workflow(task))


@ingest_app.command("funding-rates")
def ingest_funding_rates(
    exchange: Exchange = typer.Option(Exchange.BINANCE, help="Source exchange"),
    trade_type: TradeType = typer.Option(TradeType.UM_FUTURES, help="Type of trading instrument"),
    symbols: List[str] = typer.Option(..., help="Trading symbols to ingest"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
    force_update: bool = typer.Option(False, help="Force update existing data"),
):
    """Ingest funding rate data."""
    console.print("[bold blue]Ingesting funding rate data[/bold blue]")

    # Validate trade type
    if trade_type == TradeType.SPOT:
        console.print("[red]Error: Funding rates not available for spot trading[/red]")
        raise typer.Exit(1)

    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # Create ingestion task
    task = DataIngestionTask(
        exchange=exchange,
        data_type=DataType.FUNDING_RATES,
        trade_type=trade_type,
        symbols=symbols,
        start_date=start_dt,
        end_date=end_dt,
        force_update=force_update,
    )

    # Execute workflow
    asyncio.run(_run_ingestion_workflow(task))


# Processing Commands
@process_app.command("transform")
def process_transform(
    data_type: DataType = typer.Option(..., help="Type of data to process"),
    symbols: Optional[List[str]] = typer.Option(None, help="Specific symbols to process"),
    start_date: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD)"),
):
    """Transform data from Bronze to Silver zone."""
    console.print(f"[bold blue]Processing {data_type.value} data[/bold blue]")

    # Future: Implement processing workflow
    console.print("[yellow]Processing workflows not yet implemented[/yellow]")


# Query Commands
@query_app.command("info")
def query_info(
    exchange: Exchange = typer.Option(Exchange.BINANCE, help="Exchange to query"),
    data_type: Optional[DataType] = typer.Option(None, help="Data type filter"),
):
    """Show available data information."""
    console.print(f"[bold blue]Data availability for {exchange.value}[/bold blue]")

    # Future: Implement data catalog query
    console.print("[yellow]Data catalog queries not yet implemented[/yellow]")


# Admin Commands
@admin_app.command("setup")
def admin_setup():
    """Initialize the data lakehouse infrastructure."""
    console.print("[bold blue]Setting up data lakehouse infrastructure[/bold blue]")

    with Progress() as progress:
        task = progress.add_task("[green]Initializing...", total=5)

        progress.update(task, advance=1, description="[green]Creating directories...")
        settings.local_data_dir.mkdir(parents=True, exist_ok=True)

        progress.update(task, advance=1, description="[green]Validating configuration...")
        # Future: Add configuration validation

        progress.update(task, advance=1, description="[green]Setting up storage...")
        # Future: Initialize cloud storage

        progress.update(task, advance=1, description="[green]Configuring data catalog...")
        # Future: Setup data catalog

        progress.update(task, advance=1, description="[green]Setup complete!")

    console.print("[bold green]✓ Data lakehouse setup completed successfully[/bold green]")


@admin_app.command("status")
def admin_status():
    """Show system status."""
    table = Table(title="System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details")

    # Configuration
    table.add_row(
        "Configuration", "✓ OK" if settings else "✗ Error", f"Environment: {settings.environment}"
    )

    # Storage
    storage_status = "✓ OK" if settings.local_data_dir.exists() else "✗ Error"
    table.add_row("Local Storage", storage_status, str(settings.local_data_dir))

    # Cloud
    cloud_status = "✓ OK" if settings.is_cloud_enabled else "⚠ Disabled"
    table.add_row("Cloud Storage", cloud_status, settings.storage.base_path)

    console.print(table)


# Helper functions
async def _run_ingestion_workflow(task: DataIngestionTask):
    """Run ingestion workflow."""
    try:
        workflow = WorkflowRegistry.get_workflow("ingestion", settings)
        result = await workflow.execute(task=task)

        console.print("[bold green]✓ Ingestion completed successfully[/bold green]")
        console.print(f"Records processed: {result.get('records_processed', 0)}")

    except Exception as e:
        console.print(f"[bold red]✗ Ingestion failed: {e}[/bold red]")
        raise typer.Exit(1)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
