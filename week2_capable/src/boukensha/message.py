from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


@dataclass(repr=False)
class Message:
    role: str
    content: Union[str, List[Dict[str, Any]]]
    tool_use_id: Optional[str] = None

    def __repr__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        content_preview = str(self.content)[:61]
        return f"<Message role={self.role}{id_tag} content={content_preview}...>"

    def __str__(self) -> str:
        return self.__repr__()
