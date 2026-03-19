from dataclasses import dataclass
from typing import List, Optional


class StaFlowError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


@dataclass
class Port:
    direction: str
    name: str
    width: Optional[str] = None


@dataclass
class ClassifiedPorts:
    clock: str
    resets: List[Port]
    test_inputs: List[Port]
    async_inputs: List[Port]
    data_inputs: List[Port]
    data_outputs: List[Port]
    unconstrained_outputs: List[Port]
