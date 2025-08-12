from .openai_client import client, has_openai
from typing import List, Dict, Tuple
import base64

SYSTEM = "You are an expert nutrition assistant. Extract foods and portion sizes (in grams). Return JSON with items: [{name, grams}]. If uncertain, ask for clarification."

def parse_text_to_items(text: str) -> List[Dict]:
    # Heuristic fallback: split by commas; assume 150g each if no grams provided
    items = []
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for p in parts:
        grams = 150.0
        # try to parse like '200g' or '250 g'
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*g", p.lower())
        if m:
            grams = float(m.group(1))
            name = re.sub(r"(\d+(?:\.\d+)?)\s*g", "", p, flags=re.IGNORECASE).strip()
        else:
            name = p
        items.append({"name": name, "grams": grams})
    return items

def llm_parse_text(text: str) -> List[Dict]:
    if not has_openai():
        raise RuntimeError("OpenAI not configured")
    c = client()
    prompt = f"User text: {text}\nReturn ONLY JSON: {{\"items\":[{{\"name\":..., \"grams\":...}}]}}"
    resp = c.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system", "content": SYSTEM},
            {"role":"user", "content": prompt},
        ],
        response_format={"type":"json_object"},
        temperature=0.2
    )
    try:
        import json
        data = json.loads(resp.choices[0].message.content)
        return data.get("items", [])
    except Exception:
        # model didn't return valid JSON
        return []

def llm_text_chat(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict]]:
    """Conduct a chat with the model to negotiate items and quantities.
    Returns: (assistant_text, items)
    - assistant_text: model's last reply prompting for confirmation or acknowledging parsing
    - items: parsed [{name, grams}] if the model produced structured JSON in the last turn or earlier; else []
    """
    if not has_openai():
        raise RuntimeError("OpenAI not configured")
    c = client()
    sys = {
        "role": "system",
        "content": (
            "You are a nutrition logging assistant. Your goal is to determine exactly what the user ate and the quantities in grams. "
            "When you propose quantities, ask for confirmation. Once quantities are confirmed, return ONLY a JSON object of the form {\"items\":[{\"name\":...,\"grams\":...}]} in your final message."
        ),
    }
    chat_messages = [sys]
    chat_messages.extend(messages)
    resp = c.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_messages,
        temperature=0.2,
    )
    assistant_text = resp.choices[0].message.content or ""
    # try to extract items JSON from the assistant_text
    import json, re
    items: List[Dict] = []
    m = re.search(r"\{[\s\S]*\}", assistant_text)
    if m:
        try:
            data = json.loads(m.group(0))
            items = data.get("items", [])
        except Exception:
            items = []
    return assistant_text, items

def llm_parse_image(image_b64: str, hint_text: str | None = None) -> List[Dict]:
    if not has_openai():
        raise RuntimeError("OpenAI not configured")
    c = client()
    user_content = []
    if hint_text:
        user_content.append({"type":"text", "text": f"Hint/context: {hint_text}"})
    user_content.append({"type":"input_image", "image_data": image_b64})
    resp = c.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system", "content": SYSTEM},
            {"role":"user", "content": user_content},
        ],
        temperature=0.2
    )
    # naive JSON scrape
    import json, re
    text = resp.choices[0].message.content
    # Try to find a JSON block
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            data = json.loads(m.group(0))
            return data.get("items", [])
        except Exception:
            pass
    # fallback: nothing parsed
    return []
