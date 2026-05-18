from lore.models import PipelineContext
from lore.sources.base import SourcePlugin
from lore.parsers.base import ParserPlugin
from lore.outputs.base import OutputPlugin


class Pipeline:
    def __init__(
        self,
        source: SourcePlugin,
        parser: ParserPlugin,
        analyzer,
        output: OutputPlugin,
        schema_store=None,
    ) -> None:
        self._source = source
        self._parser = parser
        self._analyzer = analyzer
        self._output = output
        self._schema_store = schema_store

    def run(self, context: PipelineContext) -> PipelineContext:
        context = self._source.run(context)
        context = self._parser.run(context)

        if not context.migrations:
            return context

        context = self._analyzer.run(context)
        context = self._output.run(context)

        if self._schema_store is not None:
            all_changes = [c for m in context.migrations for c in m.changes]
            self._schema_store.apply(all_changes)
            self._schema_store.save()

        return context
