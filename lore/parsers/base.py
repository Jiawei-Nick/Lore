from abc import ABC, abstractmethod
from lore.models import Migration, PipelineContext


class ParserPlugin(ABC):
    @abstractmethod
    def parse(self, raw_diff: str) -> list[Migration]:
        ...

    def run(self, context: PipelineContext) -> PipelineContext:
        context.migrations = self.parse(context.raw_diff)
        return context
