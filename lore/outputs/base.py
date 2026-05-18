from abc import ABC, abstractmethod
from lore.models import PipelineContext


class OutputPlugin(ABC):
    @abstractmethod
    def run(self, context: PipelineContext) -> PipelineContext:
        ...
