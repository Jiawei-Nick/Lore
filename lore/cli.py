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
from lore.erd_categorized import generate_categorized_erds
from lore.db_introspect import introspect_database
from lore.connections import ConnectionManager

# Load environment variables from .env file
load_dotenv()

app = typer.Typer()
connections_app = typer.Typer(help="Manage database connection profiles")
app.add_typer(connections_app, name="connections")

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
        base_url=cfg.lark_base_url,
    )
    document_id, url = output.create_parent_doc(title=title)
    typer.echo(f"Created parent doc: {url}")
    typer.echo(f"document_id: {document_id}")
    typer.echo("")
    typer.echo("Next step: add this line to ~/.zshrc and restart your shell:")
    typer.echo(f"  export LARK_PARENT_DOC_ID={document_id}")
    typer.echo("Then run: lore init --db <your-db-url>")


@app.command("setup-erd-folders")
def setup_erd_folders(
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    parent_folder: str = typer.Option(None, help="Parent folder token (uses LARK_FOLDER_TOKEN from config if not provided)"),
) -> None:
    """Create both ERD folders: one for images, one for code.

    Creates:
      - "ERD Diagram" folder (for PNG image files)
      - "ERD Diagram - Mermaid Code Base" folder (for .mmd source files)

    Returns the folder tokens for use with generate-erd --upload-files.
    """
    cfg = load_config(config)
    parent = parent_folder or cfg.lark_folder_token

    if not parent:
        typer.echo("[ERROR] No parent folder specified. Provide --parent-folder or set LARK_FOLDER_TOKEN in config.")
        raise typer.Exit(1)

    output = LarkDocOutput(
        app_id=cfg.lark_app_id,
        app_secret=cfg.lark_app_secret,
        folder_token=parent,
        base_url=cfg.lark_base_url,
    )

    # Create image folder
    typer.echo("Creating 'ERD Diagram' folder...")
    try:
        image_folder_token = output.create_folder("ERD Diagram", parent)
        typer.echo(f"[OK] Created image folder: {image_folder_token}")
    except Exception as e:
        typer.echo(f"[ERROR] Failed to create image folder: {e}")
        raise typer.Exit(1)

    # Create code folder
    typer.echo("Creating 'ERD Diagram - Mermaid Code Base' folder...")
    try:
        code_folder_token = output.create_folder("ERD Diagram - Mermaid Code Base", parent)
        typer.echo(f"[OK] Created code folder: {code_folder_token}")
    except Exception as e:
        typer.echo(f"[ERROR] Failed to create code folder: {e}")
        raise typer.Exit(1)

    typer.echo("")
    typer.echo("=== Setup Complete ===")
    typer.echo("")
    typer.echo("Add these to your ~/.zshrc:")
    typer.echo(f"  export LARK_ERD_IMAGE_FOLDER={image_folder_token}")
    typer.echo(f"  export LARK_ERD_CODE_FOLDER={code_folder_token}")
    typer.echo("")
    typer.echo("Then run:")
    typer.echo("  lore generate-erd --upload --upload-files")

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
        base_url=cfg.lark_base_url,
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
    db: str = typer.Option(None, help="Database connection URL (postgresql://... or mysql://...)"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml"),
    schema_path: str = typer.Option(_DEFAULT_SCHEMA_PATH, help="Path to write lore-schema.json"),
    schema: str = typer.Option(None, help="Schema/database name (default: 'public' for PostgreSQL, auto-detected for MySQL)"),
    save_as: str = typer.Option(None, help="Save this connection with a shortcut name for later use"),
    use: str = typer.Option(None, help="Use a saved connection by name"),
) -> None:
    """Initialize schema snapshot from database.

    Usage:
      # Direct connection
      lore init --db postgresql://user:pass@host/db

      # Save connection for later
      lore init --db postgresql://user:pass@host/db --save-as prod-replica

      # Use saved connection
      lore init --use prod-replica

      # Interactive menu (if no --db or --use specified)
      lore init
    """
    conn_manager = ConnectionManager()
    actual_url = None
    connection_name = None

    # Determine which connection to use
    if use:
        # Use saved connection by name
        conn_profile = conn_manager.get(use)
        if not conn_profile:
            typer.echo(f"[ERROR] Connection '{use}' not found.")
            typer.echo("Run 'lore connections list' to see available connections.")
            raise typer.Exit(1)
        actual_url = conn_profile["url"]
        connection_name = use
        typer.echo(f"Using connection: {use}")
        typer.echo(f"Database: {conn_manager.mask_password(actual_url)}")
    elif db:
        # Direct URL provided
        actual_url = db
        if save_as:
            conn_manager.add(save_as, db)
            typer.echo(f"✓ Saved connection as '{save_as}'")
            connection_name = save_as
    else:
        # Interactive menu
        connections = conn_manager.list_all()
        if not connections:
            typer.echo("[ERROR] No database connection specified and no saved connections found.")
            typer.echo("")
            typer.echo("Usage:")
            typer.echo("  lore init --db postgresql://user:pass@host/db")
            typer.echo("  lore init --db postgresql://user:pass@host/db --save-as prod-replica")
            raise typer.Exit(1)

        typer.echo("Select a database connection:\n")
        conn_list = list(connections.items())
        for idx, (name, profile) in enumerate(conn_list, start=1):
            masked_url = conn_manager.mask_password(profile["url"])
            desc = f" - {profile['description']}" if profile.get("description") else ""
            typer.echo(f"  {idx}. {name} ({masked_url}){desc}")

        typer.echo("")
        selection = typer.prompt("Enter number", type=int)
        if selection < 1 or selection > len(conn_list):
            typer.echo("[ERROR] Invalid selection.")
            raise typer.Exit(1)

        connection_name, profile = conn_list[selection - 1]
        actual_url = profile["url"]
        typer.echo(f"\nUsing connection: {connection_name}")
        typer.echo(f"Database: {conn_manager.mask_password(actual_url)}")

    # Show actual command (with masked password)
    if connection_name:
        typer.echo(f"Command: lore init --use {connection_name}\n")
    else:
        typer.echo(f"Command: lore init --db {conn_manager.mask_password(actual_url)}\n")

    # Proceed with schema introspection
    cfg = load_config(config)
    typer.echo("Introspecting database schema...")
    tables = introspect_database(actual_url, schema)

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
        base_url=cfg.lark_base_url,
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
        base_url=cfg.lark_base_url,
    )

    pipeline = Pipeline(
        source=GitLocalSource(),
        parser=CompositeParser(),
        analyzer=ClaudeAnalyzer(
            aws_region=cfg.aws_region,
            aws_access_key_id=cfg.aws_access_key_id,
            aws_secret_access_key=cfg.aws_secret_access_key,
            aws_session_token=cfg.aws_session_token,
            aws_bearer_token=cfg.aws_bearer_token,
        ),
        output=lark_output,
        schema_store=store,
    )

    ctx = PipelineContext(repo_path=repo, branch=branch, base=base)
    result = pipeline.run(ctx)

    if not result.migrations:
        typer.echo("No DB migration changes detected in this diff.")
        return

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
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml (required if --upload)"),
    max_categories: int = typer.Option(None, help="Max categories to upload to Lark (default: no limit, uploads all renderable categories <15KB)"),
    individual: bool = typer.Option(False, "--individual", help="Upload each category ERD individually (one at a time, not batched)"),
    upload_files: bool = typer.Option(False, "--upload-files", help="Upload PNG and .mmd files directly to Lark Drive folders (recommended)"),
    folder_token: str = typer.Option(None, help="Override folder token (default: use LARK_FOLDER_TOKEN from config)"),
    image_folder: str = typer.Option(None, "--image-folder", help="Folder token for image-rendered ERDs (e.g., 'ERD Diagram' folder)"),
    code_folder: str = typer.Option(None, "--code-folder", help="Folder token for code-based ERDs (e.g., 'ERD Diagram - Mermaid Code Base' folder)"),
    doc_id: str = typer.Option(None, help="Override parent document ID (default: use LARK_PARENT_DOC_ID from config)"),
    as_code: bool = typer.Option(False, "--as-code", help="Upload ERDs as code blocks without attempting image rendering (faster)"),
) -> None:
    """Generate category-based ERD diagrams from the schema snapshot.

    Output modes:
      - Default: Save detailed ERDs to files (one .mmd file per category)
      - --upload-files: Upload PNG and .mmd files directly to Lark Drive folders (recommended)
      - --upload --individual: Upload each category separately to parent doc (one at a time)

    Examples:
      lore generate-erd --output-dir ./docs/erd                    # Save all categories to files
      lore generate-erd --upload --upload-files                    # Upload files to Lark Drive folders (recommended)
      lore generate-erd --upload --individual                      # Upload each category to parent doc
      lore generate-erd --upload --max-categories 20               # Upload only top 20 categories to parent doc

    Note: Categories >15KB are automatically skipped to avoid rendering failures.
    """
    from pathlib import Path

    store = SchemaStore(path=schema_path)
    store.load()

    if not store.tables:
        typer.echo("No schema found. Run `lore init` first to create a schema snapshot.")
        raise typer.Exit(1)

    # Generate ERD content for all categories
    from lore.erd_categorized import _categorize_tables, _generate_erd_for_category
    categories = _categorize_tables(store.tables)
    erd_map = {cat: _generate_erd_for_category(store.tables, cat, tables)
               for cat, tables in categories.items()}

    # Output to files if requested
    if output_dir:
        # Create subdirectory for mermaid code files
        output_path = Path(output_dir)
        mermaid_dir = output_path / "ERD Diagram - Mermaid Code Base"
        mermaid_dir.mkdir(parents=True, exist_ok=True)

        for category, content in erd_map.items():
            file_path = mermaid_dir / f"{category}.mmd"
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
        target_folder = folder_token or cfg.lark_folder_token
        lark_output = LarkDocOutput(
            app_id=cfg.lark_app_id,
            app_secret=cfg.lark_app_secret,
            folder_token=target_folder,
            parent_doc_id=target_doc_id,
            base_url=cfg.lark_base_url,
        )

        if upload_files:
            # Upload PNG and .mmd files directly to Lark Drive folders
            img_folder = image_folder or cfg.lark_erd_image_folder
            cod_folder = code_folder or cfg.lark_erd_code_folder

            if not img_folder or not cod_folder:
                typer.echo("[ERROR] Both --image-folder and --code-folder are required for --upload-files")
                typer.echo("Run 'lore setup-erd-folders' first to create the folders.")
                raise typer.Exit(1)

            uploaded_pngs, uploaded_mmds = lark_output.upload_erd_files_to_folders(
                erd_map,
                image_folder_token=img_folder,
                code_folder_token=cod_folder
            )
            typer.echo(f"[OK] Uploaded {len(uploaded_pngs)} PNG files to 'ERD Diagram' folder")
            typer.echo(f"[OK] Uploaded {len(uploaded_mmds)} .mmd files to 'ERD Diagram - Mermaid Code Base' folder")
            typer.echo("")
            typer.echo("Sample PNG files:")
            for filename in uploaded_pngs[:10]:
                typer.echo(f"  - {filename}")
            if len(uploaded_pngs) > 10:
                typer.echo(f"  ... and {len(uploaded_pngs) - 10} more")
            typer.echo("")
            typer.echo("Sample .mmd files:")
            for filename in uploaded_mmds[:10]:
                typer.echo(f"  - {filename}")
            if len(uploaded_mmds) > 10:
                typer.echo(f"  ... and {len(uploaded_mmds) - 10} more")
        elif individual:
            lark_output.upload_individual_category_erds(erd_map, page_token=target_doc_id, as_code=as_code)
            doc_url = f"https://{cfg.lark_base_url}/docx/{target_doc_id}"
            mode = "code blocks" if as_code else "images/code blocks"
            typer.echo(f"[OK] Uploaded individual category ERDs ({mode}) to Lark: {doc_url}")
        else:
            lark_output.upload_category_erds(erd_map, page_token=target_doc_id, max_categories=max_categories)
            doc_url = f"https://{cfg.lark_base_url}/docx/{target_doc_id}"
            typer.echo(f"[OK] Uploaded top {min(max_categories, len(erd_map))} category ERDs to Lark: {doc_url}")
            if len(erd_map) > max_categories:
                typer.echo(f"  (showing top {max_categories} of {len(erd_map)} categories by table count)")

    # Help message if no output specified
    if not output_dir and not upload:
        typer.echo("[WARN] No output specified. Use --output-dir or --upload to save/upload ERDs.")
        typer.echo("   Examples:")
        typer.echo("     lore generate-erd --output-dir ./docs/erd")
        typer.echo("     lore generate-erd --upload")


# === Database Connection Management Commands ===

@connections_app.command("list")
def connections_list() -> None:
    """List all saved database connections."""
    conn_manager = ConnectionManager()
    connections = conn_manager.list_all()

    if not connections:
        typer.echo("No saved connections found.")
        typer.echo("")
        typer.echo("Save a connection with:")
        typer.echo("  lore init --db postgresql://user:pass@host/db --save-as prod-replica")
        return

    typer.echo(f"Saved connections ({len(connections)}):\n")
    for name, profile in connections.items():
        masked_url = conn_manager.mask_password(profile["url"])
        desc = f" - {profile['description']}" if profile.get("description") else ""
        typer.echo(f"  • {name}")
        typer.echo(f"    {masked_url}{desc}")
        typer.echo("")


@connections_app.command("add")
def connections_add(
    name: str = typer.Argument(..., help="Connection name (e.g., prod-replica)"),
    url: str = typer.Option(..., "--db", help="Database connection URL"),
    description: str = typer.Option("", "--desc", help="Optional description"),
) -> None:
    """Add a new database connection profile."""
    conn_manager = ConnectionManager()
    conn_manager.add(name, url, description)
    typer.echo(f"✓ Saved connection '{name}'")
    typer.echo(f"  Database: {conn_manager.mask_password(url)}")
    if description:
        typer.echo(f"  Description: {description}")


@connections_app.command("edit")
def connections_edit(
    name: str = typer.Argument(..., help="Connection name to edit"),
    url: str = typer.Option(None, "--db", help="New database connection URL"),
    description: str = typer.Option(None, "--desc", help="New description"),
) -> None:
    """Edit an existing database connection profile."""
    conn_manager = ConnectionManager()
    profile = conn_manager.get(name)

    if not profile:
        typer.echo(f"[ERROR] Connection '{name}' not found.")
        typer.echo("Run 'lore connections list' to see available connections.")
        raise typer.Exit(1)

    # Update fields if provided
    if url:
        profile["url"] = url
    if description is not None:
        profile["description"] = description

    conn_manager.add(name, profile["url"], profile.get("description", ""))
    typer.echo(f"✓ Updated connection '{name}'")
    typer.echo(f"  Database: {conn_manager.mask_password(profile['url'])}")
    if profile.get("description"):
        typer.echo(f"  Description: {profile['description']}")


@connections_app.command("remove")
def connections_remove(
    name: str = typer.Argument(..., help="Connection name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Remove a saved database connection profile."""
    conn_manager = ConnectionManager()
    profile = conn_manager.get(name)

    if not profile:
        typer.echo(f"[ERROR] Connection '{name}' not found.")
        typer.echo("Run 'lore connections list' to see available connections.")
        raise typer.Exit(1)

    # Show what will be removed
    typer.echo(f"Connection to remove: {name}")
    typer.echo(f"  Database: {conn_manager.mask_password(profile['url'])}")
    if profile.get("description"):
        typer.echo(f"  Description: {profile['description']}")
    typer.echo("")

    # Confirm deletion
    if not yes:
        confirm = typer.confirm("Are you sure you want to remove this connection?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit(0)

    conn_manager.remove(name)
    typer.echo(f"✓ Removed connection '{name}'")
