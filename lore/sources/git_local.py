import git
from lore.models import PipelineContext
from lore.sources.base import SourcePlugin


class GitLocalSource(SourcePlugin):
    def run(self, context: PipelineContext) -> PipelineContext:
        try:
            repo = git.Repo(context.repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"{context.repo_path} is not a git repository")

        base_commit = repo.commit(context.base)
        feature_commit = repo.commit(context.branch)
        diff = repo.git.diff(base_commit.hexsha, feature_commit.hexsha)
        context.raw_diff = diff
        return context
