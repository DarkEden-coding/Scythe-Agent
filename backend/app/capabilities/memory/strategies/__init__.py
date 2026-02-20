from app.capabilities.memory.strategies.compact import CompactMemoryStrategy
from app.capabilities.memory.strategies.observational import ObservationalMemoryStrategy


def get_memory_strategy(mode: str):
    if mode == "observational":
        return ObservationalMemoryStrategy()
    return CompactMemoryStrategy()
