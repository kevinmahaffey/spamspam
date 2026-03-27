"""Claude API integration for generating absurd spam responses.

Supports two backends:
  1. anthropic SDK with API key (ANTHROPIC_API_KEY) - standard pay-per-use
  2. claude-agent-sdk with OAuth (Claude Max/Pro plans) - uses your subscription
"""

import asyncio

RESPONSE_RULES = """
RULES:
- Never reveal you are an AI, bot, or automated system
- Never use emoji excessively (one occasionally is fine)
- Keep the spammer engaged and talking as long as possible
- Ask questions that require them to respond
- Be entertaining and create ridiculous situations
- If they ask for money, bank info, SSN, or personal details, deflect hilariously
- Gradually escalate the absurdity over the course of the conversation
- Respond in plain text only, no markdown formatting
- Match the casual tone of text messaging - use contractions, informal language
- Occasionally make typos or use text speak to seem more human
- NEVER give real personal information of any kind
"""


def create_generator(use_oauth: bool = False, api_key: str | None = None):
    """Create the appropriate response generator.

    Args:
        use_oauth: If True, use Claude Agent SDK with OAuth (for Max/Pro plans).
        api_key: API key for the anthropic SDK. Falls back to ANTHROPIC_API_KEY env var.
    """
    if use_oauth:
        return OAuthResponseGenerator()
    return APIKeyResponseGenerator(api_key=api_key)


class APIKeyResponseGenerator:
    """Generate responses using the anthropic SDK with an API key."""

    def __init__(self, api_key: str | None = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required. Install it with:\n"
                "  pip install anthropic"
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_reply(
        self,
        persona: dict,
        conversation_history: list[dict],
        incoming_message: str,
    ) -> str:
        """Generate an absurd response as the given persona."""
        system_prompt = f"{persona['system']}\n\n{RESPONSE_RULES}"

        messages = list(conversation_history) + [
            {"role": "user", "content": incoming_message}
        ]

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text


class OAuthResponseGenerator:
    """Generate responses using the Claude Agent SDK with OAuth.

    Uses your Claude Max/Pro subscription via Claude Code's OAuth session.
    No API key needed.
    """

    def __init__(self):
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
            self._query = query
            self._options_cls = ClaudeAgentOptions
            self._result_cls = ResultMessage
        except ImportError:
            raise ImportError(
                "The 'claude-agent-sdk' package is required for OAuth mode.\n"
                "Install it with:\n"
                "  pip install claude-agent-sdk\n\n"
                "You must also be logged into Claude Code (run 'claude' once to authenticate)."
            )

    def generate_reply(
        self,
        persona: dict,
        conversation_history: list[dict],
        incoming_message: str,
    ) -> str:
        """Generate an absurd response as the given persona."""
        system_prompt = f"{persona['system']}\n\n{RESPONSE_RULES}"

        # Build a prompt that includes conversation history for context
        history_text = ""
        if conversation_history:
            for msg in conversation_history:
                role = "Spammer" if msg["role"] == "user" else "You"
                history_text += f"{role}: {msg['content']}\n"

        prompt = (
            f"{system_prompt}\n\n"
            f"Previous conversation:\n{history_text}\n"
            f"Spammer's latest message: {incoming_message}\n\n"
            f"Reply in character as {persona['name']}. "
            f"Just the reply text, nothing else."
        )

        return asyncio.run(self._generate_async(prompt))

    async def _generate_async(self, prompt: str) -> str:
        """Run the agent SDK query asynchronously."""
        result_text = ""
        async for message in self._query(
            prompt=prompt,
            options=self._options_cls(
                allowed_tools=[],
                max_turns=1,
            ),
        ):
            if isinstance(message, self._result_cls):
                result_text = message.result
        return result_text.strip()
