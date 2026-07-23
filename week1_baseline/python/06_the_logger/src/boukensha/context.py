from typing import Any, Dict, List, Optional, Type, Union

from .message import Message


class Context:
    def __init__(self, task: Optional[Type] = None, system: Optional[str] = None):
        self.task: Optional[Type] = task
        self.system: Optional[str] = system
        self.messages: list = []
        self.tools: Dict[str, Any] = {}

    def register_tool(self, tool: Any) -> None:
        self.tools[tool.name] = tool

    def add_message(
        self,
        role: str,
        content: Union[str, List[Dict[str, Any]]],
        tool_use_id: Optional[str] = None,
    ) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def tool_count(self) -> int:
        return len(self.tools)

    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        task_name = None
        if self.task:
            # Handle both regular methods and classmethods
            try:
                task_name = self.task.task_name()
            except TypeError:
                # If it's already a property or attribute, try accessing directly
                task_name = getattr(self.task, 'task_name', None)
        return f"<Context task={task_name} turns={self.turn_count()} tools={self.tool_count()}>"

    def __str__(self) -> str:
        return self.__repr__()
