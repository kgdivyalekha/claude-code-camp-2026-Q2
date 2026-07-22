from typing import Any, Dict, Optional, Type


class Context:
    def __init__(self, task: Optional[Type] = None, system: Optional[str] = None):
        self.task: Optional[Type] = task
        self.system: Optional[str] = system
        self.messages: list = []
        self.tools: Dict[str, Any] = {}

    def register_tool(self, tool: Any) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, tool_use_id: Optional[str] = None) -> None:
        # Import Message here to avoid circular dependency at module load time
        import sys
        if 'message' in sys.modules:
            MessageClass = sys.modules['message'].Message
        else:
            from importlib.util import spec_from_file_location, module_from_spec
            from pathlib import Path
            message_path = Path(__file__).parent / "message.py"
            spec = spec_from_file_location("message_internal", message_path)
            message_module = module_from_spec(spec)
            spec.loader.exec_module(message_module)
            MessageClass = message_module.Message
        
        self.messages.append(MessageClass(role, content, tool_use_id))

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
