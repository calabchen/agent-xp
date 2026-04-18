from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有工具的抽象基类定义"""

    def __init__(self, name: str, description: str):
        if not isinstance(name, str):
            raise ValueError("Tool name must be a string.")

        self._name = name.lower()
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @abstractmethod
    def run(self, query: str) -> Any:
        pass
