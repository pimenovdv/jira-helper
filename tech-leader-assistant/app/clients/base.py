from abc import ABC, abstractmethod

class BaseClient(ABC):
    @abstractmethod
    def ping(self) -> dict:
        pass
