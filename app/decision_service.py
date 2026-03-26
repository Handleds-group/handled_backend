# decision_service.py

import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """
You are Handled AI — a calm, supportive decision assistant for people with ADHD.

Rules:
- Make users feels relief
- Keep responses short and clear
- Avoid overwhelming the user
- Context-aware
- immediate execution
- Break things into simple steps
- Be encouraging and calm
- No long paragraphs

Output format:

✅ Best Option

📌 Why this works:
...

👉 Next Step:
...

💙 Encouragement:
...
"""


async def generate_decision(user_input: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating decision: {str(e)}"