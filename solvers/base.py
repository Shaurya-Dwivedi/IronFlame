import abc
from typing import Generator

class BaseSolver(abc.ABC):
    """Abstract Base Class for Multimodal AI Solvers."""

    @abc.abstractmethod
    def solve_screenshot_stream(self, screenshot_path: str, user_prompt: str) -> Generator[str, None, None]:
        """
        Takes a screenshot path and a prompt, sends it to the AI model,
        and yields text tokens as they arrive.
        
        Args:
            screenshot_path: Path to the saved screenshot image file.
            user_prompt: A custom prompt or context string for the AI.
            
        Yields:
            str: Chunks of the text response.
        """
        pass
