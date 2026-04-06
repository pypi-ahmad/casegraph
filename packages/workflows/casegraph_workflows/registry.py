"""Typed workflow registry."""

from __future__ import annotations

from casegraph_workflows.schemas import WorkflowDefinition


class WorkflowRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, WorkflowDefinition] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        self._definitions[definition.id] = definition

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._definitions.get(workflow_id)

    def list_definitions(self) -> list[WorkflowDefinition]:
        return list(self._definitions.values())

    def list_ids(self) -> list[str]:
        return list(self._definitions.keys())


workflow_registry = WorkflowRegistry()
