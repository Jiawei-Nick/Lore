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


@app.command("setup-erd-folder")
def setup_erd_folder(
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    parent_folder: str = typer.Option(..., help="Parent folder token (e.g., OiX7fbnIWldTCSdqDSKlWjPygMg for 'Lore Sync')"),
    subfolder_name: str = typer.Option("ERD Diagram", help="Subfolder name to create"),
    document_id: str = typer.Option(..., help="Document ID to move into the subfolder"),
) -> None:
    """Create a subfolder and move a document into it.

    Example:
      lore setup-erd-folder --parent-folder OiX7fbnIWldTCSdqDSKlWjPygMg \\
                            --subfolder-name "ERD Diagram" \\
                            --document-id FQlEd6sEYoEiudxpVQ0l9SNvgEg
    """
    cfg = load_config(config)
    output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=cfg.lark_folder_token,
    )

    typer.echo(f"Creating subfolder '{subfolder_name}' in parent folder...")
    subfolder_token = output.create_folder(name=subfolder_name, parent_folder_token=parent_folder)
    typer.echo(f"✓ Subfolder created with token: {subfolder_token}")

    typer.echo(f"\nMoving document {document_id} to subfolder...")
    output.move_document_to_folder(document_id=document_id, target_folder_token=subfolder_token)
    typer.echo(f"✓ Document moved successfully")
    typer.echo(f"\nDocument is now in: 'Lore Sync' / '{subfolder_name}'")


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
            typer.echo(f"[WARN] ERD update failed: {e}")
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
        analyzer=ClaudeAnalyzer(
            aws_region=cfg.aws_region,
            aws_access_key_id=cfg.aws_access_key_id,
            aws_secret_access_key=cfg.aws_secret_access_key,
            aws_session_token=cfg.aws_session_token,
        ),
        output=lark_output,
        schema_store=store,
    )

    ctx = PipelineContext(repo_path=repo, branch=branch, base=base)
    result = pipeline.run(ctx)

    if not result.migrations:
        typer.echo("No DB migration changes detected in this diff.")
        return

    # Overview ERD → parent page (uses store.tables which is now updated by pipeline)
    overview_erd = generate_category_overview(store.tables)
    try:
        lark_output.update_erd_page(overview_erd, page_token=cfg.lark_parent_doc_id)
        typer.echo("Overview ERD updated on parent page.")
    except RuntimeError as e:
        typer.echo(f"[WARN] Overview ERD update failed: {e}")

    # Focused ERD → sub-page (generated AFTER pipeline so schema store is updated)
    modified_tables = {change.table for migration in result.migrations for change in migration.changes}
    focused_erd = generate_mermaid_erd(store.tables, modified_tables=modified_tables)
    sub_doc_id = result.output_url.rstrip("/").split("/")[-1] if result.output_url else None
    try:
        lark_output.append_erd_to_doc(sub_doc_id, focused_erd)
        typer.echo(f"Focused ERD appended to analysis doc ({len(modified_tables)} modified tables).")
    except RuntimeError as e:
        typer.echo(f"[WARN] Focused ERD append failed: {e}")

    if result.analysis:
        typer.echo(f"Risk: {result.analysis.risk_level.value}")
        typer.echo(f"Summary: {result.analysis.summary}")
    typer.echo(f"Lark Doc: {result.output_url}")


@app.command("generate-erd")
def generate_erd_command(
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to lore-schema.json"),
    output_dir: str = typer.Option(None, help="Directory to write ERD .mmd files (optional)"),
    upload: bool = typer.Option(False, "--upload", help="Upload ERDs to Lark parent document"),
    overview: bool = typer.Option(False, "--overview", help="Generate category overview instead of detailed ERDs"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml (required if --upload)"),
    max_categories: int = typer.Option(None, help="Max categories to upload to Lark (default: no limit, uploads all renderable categories <15KB)"),
    individual: bool = typer.Option(False, "--individual", help="Upload each category ERD individually (one at a time, not batched)"),
    doc_id: str = typer.Option(None, help="Override parent document ID (default: use LARK_PARENT_DOC_ID from config)"),
    as_code: bool = typer.Option(False, "--as-code", help="Upload ERDs as code blocks without attempting image rendering (faster)"),
) -> None:
    """Generate category-based ERD diagrams from the schema snapshot.

    Output modes:
      - Default: Save detailed ERDs to files (one .mmd file per category)
      - --overview: Generate high-level category relationship diagram
      - --upload: Upload ERDs to Lark parent document (automatically renders categories <15KB as images)
      - --individual: Upload each category separately (one at a time, not batched)

    Examples:
      lore generate-erd --output-dir ./docs/erd                    # Save all categories to files
      lore generate-erd --overview --output-dir ./docs/erd         # Save overview to file
      lore generate-erd --upload                                   # Upload all renderable categories as images (batched)
      lore generate-erd --upload --individual                      # Upload each category separately
      lore generate-erd --upload --max-categories 20               # Upload only top 20 renderable categories
      lore generate-erd --upload --overview                        # Upload overview diagram

    Note: Categories >15KB are automatically skipped to avoid rendering failures.
          Bot feature must be enabled in Lark app to upload images.
    """
    from pathlib import Path

    store = SchemaStore(path=schema_path)
    store.load()

    if not store.tables:
        typer.echo("No schema found. Run `lore init` first to create a schema snapshot.")
        raise typer.Exit(1)

    # Generate ERD content
    if overview:
        overview_content = generate_category_overview(store.tables)
        erd_content = overview_content
        erd_type = "overview"
    else:
        from lore.erd_categorized import _categorize_tables, _generate_erd_for_category
        categories = _categorize_tables(store.tables)
        erd_map = {cat: _generate_erd_for_category(store.tables, cat, tables)
                   for cat, tables in categories.items()}
        erd_type = "detailed"

    # Output to files if requested
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if overview:
            overview_file = output_path / "erd_overview.mmd"
            overview_file.write_text(overview_content)
            typer.echo(f"[OK] Saved category overview: {overview_file}")
        else:
            for category, content in erd_map.items():
                file_path = output_path / f"erd_{category}.mmd"
                file_path.write_text(content)
            typer.echo(f"[OK] Saved {len(erd_map)} category ERDs to {output_path}/")
            typer.echo("")
            typer.echo("Top categories by table count:")
            sorted_cats = sorted(erd_map.items(), key=lambda x: x[1].count(" {"), reverse=True)[:10]
            for category, content in sorted_cats:
                table_count = content.count(" {")
                typer.echo(f"  - {category:15s} ({table_count:3d} tables)")

    # Upload to Lark if requested
    if upload:
        cfg = load_config(config)
        target_doc_id = doc_id or cfg.lark_parent_doc_id
        lark_output = LarkDocOutput(
            app_id=cfg.lark_app_id,
            app_secret=cfg.lark_app_secret,
            folder_token=cfg.lark_folder_token,
            parent_doc_id=target_doc_id,
        )

        if overview:
            lark_output.update_erd_page(overview_content, page_token=target_doc_id)
            doc_url = f"https://open.larksuite.com/docx/{target_doc_id}"
            typer.echo(f"[OK] Uploaded category overview to Lark: {doc_url}")
        elif individual:
            lark_output.upload_individual_category_erds(erd_map, page_token=target_doc_id, as_code=as_code)
            doc_url = f"https://open.larksuite.com/docx/{target_doc_id}"
            mode = "code blocks" if as_code else "images/code blocks"
            typer.echo(f"[OK] Uploaded individual category ERDs ({mode}) to Lark: {doc_url}")
        else:
            lark_output.upload_category_erds(erd_map, page_token=target_doc_id, max_categories=max_categories)
            doc_url = f"https://open.larksuite.com/docx/{target_doc_id}"
            typer.echo(f"[OK] Uploaded top {min(max_categories, len(erd_map))} category ERDs to Lark: {doc_url}")
            if len(erd_map) > max_categories:
                typer.echo(f"  (showing top {max_categories} of {len(erd_map)} categories by table count)")

    # Help message if no output specified
    if not output_dir and not upload:
        typer.echo("[WARN] No output specified. Use --output-dir or --upload to save/upload ERDs.")
        typer.echo("   Examples:")
        typer.echo("     lore generate-erd --output-dir ./docs/erd")
        typer.echo("     lore generate-erd --upload")
