"""LLM answer generation via Anthropic Claude."""

import anthropic
from loguru import logger

from app.core.config import settings


class LLMService:
    """Generate RAG answers using Claude (e.g. Haiku) with a financial-RAG system prompt."""

    def __init__(self) -> None:
        """Initialize the async Anthropic client and system prompt."""
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        self.system_prompt = (
            "You are a financial RAG Analysis Agent powered by Claude Haiku 4.5. "
            "Your goal is to provide lightning-fast, highly accurate responses based "
            "strictly on the provided context.\n\n"
            "OPERATING GUIDELINES:\n"
            "1. CONTEXTUAL FIDELITY: Only use the provided <context> tags to answer. "
            "If the answer isn't there, simply say: 'Information not available in current documents.'\n"
            "2. SPEED-OPTIMIZED CITATIONS: Use concise inline citations like [source_file.pdf].\n"
            "3. FORMATTING: Use Markdown headers and bullet points for readability.\n"
            "4. PRECISION: Maintain the exact numerical values found in the context (no rounding unless specified).\n"
            "5. NO CONVERSATIONAL FILLER: Do not say 'Based on the documents...' or 'I hope this helps.' "
            "Start the answer immediately."
        )

    async def generate_answer(self, query: str, context: str) -> str:
        """Call Claude with the given query and retrieved context.

        Wraps context in <context> tags and uses the configured system prompt.
        On API errors, returns a generic SERVICE_ERROR message.

        Args:
            query: User question.
            context: Retrieved and reranked document chunks.

        Returns:
            Model-generated answer string, or SERVICE_ERROR message on failure.
        """
        try:
            logger.info(f"Invoking Claude Haiku 4.5 for query: {query[:50]}...")

            # Wrapping the context in XML-style tags as Claude 4.5 models are trained to recognise these boundaries for higher accuracy
            prompt_content = (
                f"Here is the retrieved document context:\n"
                f"<context>\n{context}\n</context>\n\n"
                f"USER QUESTION: {query}"
            )

            response = await self.client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=1024,
                temperature=0.0,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": prompt_content}
                ]
            )

            answer = response.content[0].text
            return answer

        except anthropic.APIError as e:
            # Do not call str(e) or access e.type / e.message - Anthropic error objects can raise KeyError when stringified or when those attributes are read
            try:
                status_code = getattr(e, 'status_code', None)
            except Exception:
                status_code = None
            try:
                logger.error("Anthropic API error (see traceback)", exc_info=True)
            except Exception:
                pass
            if status_code == 404:
                return f"SERVICE_ERROR: Model '{settings.LLM_MODEL}' not found. Please check your model configuration."
            else:
                return "SERVICE_ERROR: Unable to generate a response. Please try again or check the server logs."
        except (KeyError, AttributeError, TypeError) as e:
            logger.error(
                f"Error parsing API response or error object: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            return "SERVICE_ERROR: Unable to generate a response. Please try again or check the server logs."
        except Exception as e:
            logger.error(
                f"Unexpected error in LLM service: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            return f"SERVICE_ERROR: Unable to generate a response. Error: {str(e)[:100]}"

llm_service = LLMService()