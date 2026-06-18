import os
import json
import base64
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

EXTRACTION_PROMPT = """You are an invoice data extraction specialist.

Analyze this invoice PDF and return ONLY a valid JSON object — no markdown, no prose, no code fences.

JSON schema (use null for any field not present in the document):
{
  "invoice_number": "invoice/bill number string",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "payment_terms": "e.g. Net 30, Due on Receipt, or null",

  "vendor_name": "company or person issuing the invoice",
  "vendor_address": "full address of the vendor or null",
  "vendor_email": "vendor email or null",
  "vendor_phone": "vendor phone or null",
  "vendor_tax_id": "GST/VAT/EIN/Tax ID number or null",

  "bill_to_name": "company or person being billed",
  "bill_to_address": "billing address or null",

  "currency": "three-letter code, default USD",
  "subtotal": numeric or null,
  "tax_rate": numeric percentage as decimal e.g. 0.085 for 8.5% or null,
  "tax_amount": numeric or null,
  "discount_amount": numeric or null,
  "total_amount": numeric grand total or null,

  "notes": "any payment notes, special instructions, or null",

  "line_items": [
    {
      "description": "product or service description",
      "item_code": "SKU, part number, or null",
      "quantity": numeric or null,
      "unit_of_measure": "each, hr, kg, box, etc. or null",
      "unit_price": numeric or null,
      "total_price": numeric or null
    }
  ]
}"""


def parse_invoice_text(text: str) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"{EXTRACTION_PROMPT}\n\nInvoice text:\n{text}",
        }],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def parse_invoice_file(file_bytes: bytes, filename: str) -> dict:
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    media_type = MIME_TYPES.get(ext, "application/pdf")
    is_image = media_type.startswith("image/")

    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    if is_image:
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    file_block,
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
