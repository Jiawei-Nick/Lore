import typer
from dotenv import load_dotenv
from lore.config import load_config
from lore.models import PipelineContext
from lore.pipeline import Pipeline
from lore.sources.git_local import GitLocalSource
from lore.parsers.composite import CompositeParser
from lore.analyzer.claude import ClaudeAnalyzer
from lore.outputs.lark_doc import LarkDocOutput
from lore.schema_store import SchemaStore
from lore.erd import generate_mermaid_erd
from lore.erd_categorized import generate_categorized_erds, generate_category_overview
from lore.db_introspect import introspect_database

# Load environment variables from .env file
load_dotenv()

app = typer.Typer()

_DEFAULT_SCHEMA_PATH = "lore-schema.json"


@app.command("init-parent")
def init_parent(
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    title: str = typer.Option("Lore — Schema ERD", help="Title for the new parent doc"),
) -> None:
    """Create a new Lark Doc owned by the bot to use as the ERD parent doc.

    Use this when the bot can't be added as an editor on an existing doc.
    """
    cfg = load_config(config)
    output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=cfg.lark_folder_token,
    )
    document_id, url = output.create_parent_doc(title=title)
    typer.echo(f"Created parent doc: {url}")
    typer.echo(f"document_id: {document_id}")
    typer.echo("")
    typer.echo("Next step: add this line to ~/.zshrc and restart your shell:")
    typer.echo(f"  export LARK_PARENT_DOC_ID={document_id}")
    typer.echo("Then run: lore init --db <your-db-url>")


@app.command()
def init(
    db: str = typer.Option(..., help="Database connection URL (postgresql://... or mysql://...)"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to write lore-schema.json"),
    schema: str = typer.Option(None, help="Schema/database name (default: 'public' for PostgreSQL, auto-detected for MySQL)"),
) -> None:
    cfg = load_config(config)
    typer.echo("Introspecting database schema...")
    tables = introspect_database(db, schema)

    store = SchemaStore(path=schema_path)
    store.tables = tables
    store.save()
    typer.echo(f"Schema snapshot saved to {schema_path} ({len(tables)} tables)")

    # Generate ERD with smart filtering if needed
    erd = generate_mermaid_erd(tables)
    output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=cfg.lark_folder_token,
        parent_doc_id=cfg.lark_parent_doc_id,
    )

    try:
        output.update_erd_page(erd, page_token=cfg.lark_parent_doc_id)
        typer.echo(f"ERD updated on Lark Doc parent page ({len(tables)} tables).")
    except RuntimeError as e:
        if "too many chars" in str(e):
            typer.echo(f"⚠️  ERD update failed: {e}")
        else:
            raise


@app.command()
def analyze(
    repo: str = typer.Option("./", help="Path to the git repository"),
    branch: str = typer.Option(..., help="Feature branch to analyze"),
    base: str = typer.Option("main", help="Base branch to diff against"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml config file"),
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to lore-schema.json"),
) -> None:
    cfg = load_config(config)

    store = SchemaStore(path=schema_path)
    store.load()

    lark_output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=cfg.lark_folder_token,
        parent_doc_id=cfg.lark_parent_doc_id,
    )

    pipeline = Pipeline(
        source=GitLocalSource(),
        parser=CompositeParser(),
        analyzer=ClaudeAnalyzer(aws_bearer_token=cfg.aws_bearer_token, aws_region=cfg.aws_region),
        output=lark_output,
        schema_store=store,
    )

    ctx = PipelineContext(repo_path=repo, branch=branch, base=base)
    result = pipeline.run(ctx)

    if not result.migrations:
        typer.echo("No DB migration changes detected in this diff.")
        return

    # Extract modified table names from migrations
    modified_tables = {change.table for migration in result.migrations for change in migration.changes}

    # Generate ERD focused on modified tables
    erd = generate_mermaid_erd(store.tables, modified_tables=modified_tables)
    try:
        lark_output.update_erd_page(erd, page_token=cfg.lark_parent_doc_id)
        typer.echo(f"ERD updated on parent page (showing {len(modified_tables)} modified tables + related).")
    except RuntimeError as e:
        if "too many chars" in str(e):
            typer.echo(f"⚠️  ERD update failed: {e}")
        else:
            raise

    typer.echo(f"Risk: {result.analysis.risk_level.value}")
    typer.echo(f"Summary: {result.analysis.summary}")
    typer.echo(f"Lark Doc: {result.output_url}")


@app.command("generate-erd")
def generate_erd_command(
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to lore-schema.json"),
    output_dir: str = typer.Option("./erd_output", help="Directory to write ERD files"),
    overview: bool = typer.Option(False, help="Generate category overview ERD"),
) -> None:
    """Generate category-based ERD files from the schema snapshot.

    Creates separate .mmd (Mermaid) files for each category (wallet, user, card, etc.).
    Each category ERD includes only tables from that category plus cross-category
    reference annotations.

    Use --overview to generate a high-level ERD showing categories and their relationships.
    """
    from pathlib import Path

    store = SchemaStore(path=schema_path)
    store.load()

    if not store.tables:
        typer.echo("No schema found. Run `lore init` first to create a schema snapshot.")
        raise typer.Exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if overview:
        # Generate overview ERD
        overview_content = generate_category_overview(store.tables)
        overview_file = output_path / "erd_overview.mmd"
        overview_file.write_text(overview_content)
        typer.echo(f"✓ Generated category overview: {overview_file}")
        typer.echo(f"  View at: https://mermaid.live/edit#{overview_content[:100]}...")
    else:
        # Generate per-category ERDs
        erd_map = generate_categorized_erds(store.tables, output_dir=str(output_path))
        typer.echo(f"✓ Generated {len(erd_map)} category ERDs in {output_path}/")
        typer.echo("")
        typer.echo("Categories:")
        for category, content in sorted(erd_map.items()):
            table_count = content.count(" {")
            typer.echo(f"  - {category:15s} ({table_count:3d} tables) → erd_{category}.mmd")

        typer.echo("")
        typer.echo(f"To view ERDs, upload .mmd files to https://mermaid.live or use a Mermaid viewer.")
