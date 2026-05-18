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
from lore.db_introspect import introspect_postgres

# Load environment variables from .env file
load_dotenv()

app = typer.Typer()

_DEFAULT_SCHEMA_PATH = "lore-schema.json"


@app.command()
def init(
    db: str = typer.Option(..., help="PostgreSQL connection URL"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to write lore-schema.json"),
) -> None:
    cfg = load_config(config)
    typer.echo("Introspecting database schema...")
    tables = introspect_postgres(db)

    store = SchemaStore(path=schema_path)
    store.tables = tables
    store.save()
    typer.echo(f"Schema snapshot saved to {schema_path} ({len(tables)} tables)")

    erd = generate_mermaid_erd(tables)
    output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=cfg.lark_folder_token,
        parent_doc_id=cfg.lark_parent_doc_id,
    )
    output.update_erd_page(erd, page_token=cfg.lark_parent_doc_id)
    typer.echo("ERD updated on Lark Doc parent page.")


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
        analyzer=ClaudeAnalyzer(api_key=cfg.anthropic_api_key),
        output=lark_output,
        schema_store=store,
    )

    ctx = PipelineContext(repo_path=repo, branch=branch, base=base)
    result = pipeline.run(ctx)

    if not result.migrations:
        typer.echo("No DB migration changes detected in this diff.")
        return

    erd = generate_mermaid_erd(store.tables)
    lark_output.update_erd_page(erd, page_token=cfg.lark_parent_doc_id)

    typer.echo(f"Risk: {result.analysis.risk_level.value}")
    typer.echo(f"Summary: {result.analysis.summary}")
    typer.echo(f"Lark Doc: {result.output_url}")
    typer.echo("ERD updated on parent page.")
