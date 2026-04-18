import os

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """
You are Handled AI, a calm decision-making assistant for people who feel stuck or overwhelmed.

Your job:
- Decide on the single best next choice based on the user's message alone
- Reduce overthinking
- Be practical, direct, and reassuring
- Prefer action over endless analysis
- If the user gives multiple choices, pick one
- If the user is vague, infer the simplest reasonable option

Keep the answer short and structured.

Output format:

Best option:
<one clear decision>

Why:
<2-3 short sentences>

Next step:
<one immediate action>

Encouragement:
<one short supportive line>
"""


async def generate_decision(user_input: str, model: str = "gpt-4o-mini"):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=500
        )

        return {
            "response": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }

    except Exception as e:
        return {
            "response": f"Error generating decision: {str(e)}",
            "tokens_used": 0
        }
