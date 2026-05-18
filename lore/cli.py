import typer
from lore.config import load_config
from lore.models import PipelineContext
from lore.pipeline import Pipeline
from lore.sources.git_local import GitLocalSource
from lore.parsers.composite import CompositeParser
from lore.analyzer.claude import ClaudeAnalyzer
from lore.outputs.lark import LarkWikiOutput

app = typer.Typer()


@app.command()
def init() -> None:
    """Initialize lore configuration (implemented in Task 15)."""
    typer.echo("init command not yet implemented.")


@app.command()
def analyze(
    repo: str = typer.Option("./", help="Path to the git repository"),
    branch: str = typer.Option(..., help="Feature branch to analyze"),
    base: str = typer.Option("main", help="Base branch to diff against"),
    config: str = typer.Option("lore.yaml", help="Path to lore.yaml config file"),
) -> None:
    cfg = load_config(config)

    pipeline = Pipeline(
        source=GitLocalSource(),
        parser=CompositeParser(),
        analyzer=ClaudeAnalyzer(api_key=cfg.anthropic_api_key),
        output=LarkWikiOutput(
            app_id=cfg.lark_app_id,
            app_secret=cfg.lark_app_secret,
            wiki_space_id=cfg.lark_wiki_space_id,
            parent_node_token=cfg.lark_parent_node_token,
        ),
    )

    ctx = PipelineContext(repo_path=repo, branch=branch, base=base)
    result = pipeline.run(ctx)

    if not result.migrations:
        typer.echo("No DB migration changes detected in this diff.")
        return

    typer.echo(f"Risk: {result.analysis.risk_level.value}")
    typer.echo(f"Summary: {result.analysis.summary}")
    typer.echo(f"Lark Wiki page: {result.output_url}")
