STRUCTURE_SPEC = """
Return ONLY valid JSON with this schema:
{
  "reply_html": "<p>short status/html</p>",
  "items": [
    { "ingredient_name": "string", "grams": number }
  ]
}
Units: grams only. If user gives pieces/cups, convert to grams. Be conservative when unsure.
Do not include any extra keys. Ensure JSON is strictly valid.
"""

NUTRITION_CARD_SPEC = """
You must output ONLY valid JSON with:
{
  "ingredient_name": "string",
  "unit_weight": 100,
  "per_100g": {
    "calories": number,
    "protein": number,
    "carbs": number,
    "fat": number
  }
}
Rules:
- Values are for 100 g edible portion (cooked/raw as commonly consumed).
- Use globally typical values; if branded/unique, infer from public norms.
- No extra keys or text. JSON ONLY.
"""