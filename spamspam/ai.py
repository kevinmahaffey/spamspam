"""Claude API integration for generating absurd spam responses."""

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


class ResponseGenerator:
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
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
