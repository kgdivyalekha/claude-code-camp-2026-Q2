from typing import Any, ClassVar, Dict, Optional

from ..errors import UnsupportedModelError


class BackendBase:
    """Base class for LLM API backends.

    Provides model validation, metadata lookup, and cost estimation.
    Subclasses must define MODELS as a ClassVar.
    """
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {}

    def __init__(self, model: str) -> None:
        self.model: str = self.__class__.validate_model(model)
        self._model_info: Dict[str, Any] = self.__class__.model_info_for(self.model)

    @classmethod
    def models(cls) -> Dict[str, Dict[str, Any]]:
        return cls.MODELS

    @classmethod
    def model_info_for(cls, model: str) -> Optional[Dict[str, Any]]:
        return cls.MODELS.get(model)

    @classmethod
    def validate_model(cls, model: str) -> str:
        if cls.model_info_for(model):
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model '{model}'. "
            f"Supported models: {supported}"
        )

    @property
    def model_info(self) -> Dict[str, Any]:
        return self._model_info

    @property
    def context_window(self) -> int:
        return self._model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> Optional[float]:
        return self._model_info.get("cost_per_million", {}).get("input")

    @property
    def output_token_cost_per_million(self) -> Optional[float]:
        return self._model_info.get("cost_per_million", {}).get("output")

    @property
    def usage_unit(self) -> str:
        return self._model_info.get("usage_unit", "")

    @property
    def usage_level(self) -> Optional[str]:
        return self._model_info.get("usage_level")

    def estimate_cost(
        self, input_tokens: int, output_tokens: int
    ) -> Optional[float]:
        input_cost = self.input_token_cost_per_million
        output_cost = self.output_token_cost_per_million
        if input_cost is None or output_cost is None:
            return None
        return (
            (input_tokens * input_cost) + (output_tokens * output_cost)
        ) / 1_000_000.0
