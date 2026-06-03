import os
from typing import Generator
from PIL import Image
from google import genai
from google.genai import types

from solvers.base import BaseSolver

class GeminiSolver(BaseSolver):
    """Solver implementation using the official Google GenAI SDK with Gemini Multimodal Models."""

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: str = None):
        """
        Initializes the Gemini solver.
        
        Args:
            model_name: The Gemini model to use (default: gemini-2.5-flash).
            api_key: The API key. If None, it will look for GEMINI_API_KEY env variable.
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None

    @property
    def client(self) -> genai.Client:
        """Lazy-loaded Gemini GenAI client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not set. Please provide it in the .env file.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def solve_screenshot_stream(self, screenshot_path: str, user_prompt: str = "") -> Generator[str, None, None]:
        """
        Loads the screenshot, constructs the system and user instructions,
        sends it to Gemini via a streaming request, and yields text chunks.
        """
        try:
            # Open screenshot using PIL
            if not os.path.exists(screenshot_path):
                yield f"[ERROR] Screenshot file not found at: {screenshot_path}"
                return

            img = Image.open(screenshot_path)

            # System prompt to enforce structured output and metadata extraction
            system_prompt = (
                "You are an elite, concise technical interview assistant. "
                "Analyze the provided screenshot of a programming question, IDE, or code editor.\n\n"
                "CRITICAL: You MUST include metadata badges at the VERY BEGINNING of your response on the first two lines. "
                "Use EXACTLY this format:\n"
                "[TITLE: <Short Name of the Problem or Task>]\n"
                "[COMPLEXITY: Time: <Big-O> | Space: <Big-O>]\n\n"
                "After the badges, structure your response as follows:\n"
                "1. **Pattern**: Identify the key algorithmic pattern/approach in 1 sentence.\n"
                "2. **Insights**: 2-3 brief bullet points explaining the core logic, math/data structures, and edge cases to consider.\n"
                "3. **Solution**: A single markdown code block with the optimized, working code. "
                "Detect the language from the screenshot context (e.g., Python, C++, Java, JS, Go, Rust, SQL). "
                "If it's an IDE with C++ code, write C++. If it's a Python script, write Python. "
                "If not clear, default to Python. Code should be clean, highly-optimized, and contain minimal comments.\n\n"
                "Be extremely brief and direct. Avoid conversational filler like 'Sure, let's solve this' or 'Here is the solution'."
            )

            # User prompt allows adding extra context (e.g. custom user queries or instructions)
            full_user_prompt = "Solve the programming problem visible in this screenshot."
            if user_prompt:
                full_user_prompt += f"\nAdditional User Instructions: {user_prompt}"

            # List of models to try in prioritized order
            candidate_models = []
            if self.model_name:
                candidate_models.append(self.model_name)
            
            # Add fallback candidates (prioritizing 3.1-flash-lite for higher rate limits - 500 RPD)
            fallbacks = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash"]
            for m in fallbacks:
                if m not in candidate_models:
                    candidate_models.append(m)

            last_error = None
            success = False

            for model in candidate_models:
                try:
                    # Call Gemini generate_content_stream
                    response = self.client.models.generate_content_stream(
                        model=model,
                        contents=[img, full_user_prompt],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.1
                        )
                    )
                    
                    # Pull the first chunk to verify if rate limits or authentication fail
                    iterator = iter(response)
                    try:
                        first_chunk = next(iterator)
                    except StopIteration:
                        return
                    
                    success = True
                    
                    # Yield first chunk and stream the rest
                    if first_chunk.text:
                        yield first_chunk.text
                        
                    for chunk in iterator:
                        if chunk.text:
                            yield chunk.text
                    
                    # Successfully completed stream, exit model loop
                    break
                except Exception as e:
                    last_error = e
                    print(f"[Solver] Model {model} failed: {e}. Trying next model...")
                    continue
            
            if not success:
                yield f"[ERROR] Failed to communicate with Gemini API. Tried models {candidate_models}. Last error: {str(last_error)}"

        except Exception as e:
            yield f"[ERROR] Failed to communicate with Gemini API: {str(e)}"
