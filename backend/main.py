import os
from datetime import date as date_type
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

load_dotenv()

from database import engine, get_db, Base
from models import Invoice, LineItem
from claude_parser import parse_invoice_file, parse_invoice_text

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Invoice Extractor API",
    description="Upload invoice PDFs — Claude AI extracts and stores all structured data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _float(val) -> Optional[float]:
    return float(val) if val is not None else None


def _invoice_summary(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "vendor_name": inv.vendor_name,
        "bill_to_name": inv.bill_to_name,
        "total_amount": _float(inv.total_amount),
        "currency": inv.currency,
        "line_items_count": len(inv.line_items),
        "pdf_filename": inv.pdf_filename,
        "created_at": str(inv.created_at) if inv.created_at else None,
    }


def _parse_date(raw: Optional[str]) -> Optional[date_type]:
    if not raw:
        return None
    try:
        return date_type.fromisoformat(raw)
    except ValueError:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "invoice-extractor"}


@app.post("/api/invoices/upload", tags=["Invoices"])
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF invoice. Claude reads it and stores all extracted data."""
    allowed_extensions = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Only PDF and image files (PNG, JPG, WEBP) are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB).")

    try:
        parsed = parse_invoice_file(pdf_bytes, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude extraction failed: {str(e)}")

    inv = Invoice(
        invoice_number=parsed.get("invoice_number"),
        invoice_date=_parse_date(parsed.get("invoice_date")),
        due_date=_parse_date(parsed.get("due_date")),
        payment_terms=parsed.get("payment_terms"),
        vendor_name=parsed.get("vendor_name"),
        vendor_address=parsed.get("vendor_address"),
        vendor_email=parsed.get("vendor_email"),
        vendor_phone=parsed.get("vendor_phone"),
        vendor_tax_id=parsed.get("vendor_tax_id"),
        bill_to_name=parsed.get("bill_to_name"),
        bill_to_address=parsed.get("bill_to_address"),
        subtotal=parsed.get("subtotal"),
        tax_rate=parsed.get("tax_rate"),
        tax_amount=parsed.get("tax_amount"),
        discount_amount=parsed.get("discount_amount"),
        total_amount=parsed.get("total_amount"),
        currency=parsed.get("currency", "USD"),
        notes=parsed.get("notes"),
        pdf_filename=file.filename,
    )
    db.add(inv)
    db.flush()

    for item in parsed.get("line_items", []):
        db.add(LineItem(
            invoice_id=inv.id,
            description=item.get("description"),
            item_code=item.get("item_code"),
            quantity=item.get("quantity"),
            unit_of_measure=item.get("unit_of_measure"),
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
        ))

    db.commit()

    return {
        "success": True,
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "vendor": inv.vendor_name,
        "total_amount": _float(inv.total_amount),
        "currency": inv.currency,
        "line_items_count": len(parsed.get("line_items", [])),
    }


@app.post("/api/invoices/parse-text", tags=["Invoices"])
def parse_text_invoice(req: dict, db: Session = Depends(get_db)):
    """Parse invoice from pasted plain text."""
    text = (req.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        parsed = parse_invoice_text(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude extraction failed: {str(e)}")

    inv = Invoice(
        invoice_number=parsed.get("invoice_number"),
        invoice_date=_parse_date(parsed.get("invoice_date")),
        due_date=_parse_date(parsed.get("due_date")),
        payment_terms=parsed.get("payment_terms"),
        vendor_name=parsed.get("vendor_name"),
        vendor_address=parsed.get("vendor_address"),
        vendor_email=parsed.get("vendor_email"),
        vendor_phone=parsed.get("vendor_phone"),
        vendor_tax_id=parsed.get("vendor_tax_id"),
        bill_to_name=parsed.get("bill_to_name"),
        bill_to_address=parsed.get("bill_to_address"),
        subtotal=parsed.get("subtotal"),
        tax_rate=parsed.get("tax_rate"),
        tax_amount=parsed.get("tax_amount"),
        discount_amount=parsed.get("discount_amount"),
        total_amount=parsed.get("total_amount"),
        currency=parsed.get("currency", "USD"),
        notes=parsed.get("notes"),
        pdf_filename="pasted text",
    )
    db.add(inv)
    db.flush()

    for item in parsed.get("line_items", []):
        db.add(LineItem(
            invoice_id=inv.id,
            description=item.get("description"),
            item_code=item.get("item_code"),
            quantity=item.get("quantity"),
            unit_of_measure=item.get("unit_of_measure"),
            unit_price=item.get("unit_price"),
            total_price=item.get("total_price"),
        ))

    db.commit()

    return {
        "success": True,
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "vendor": inv.vendor_name,
        "total_amount": _float(inv.total_amount),
        "currency": inv.currency,
        "line_items_count": len(parsed.get("line_items", [])),
    }


@app.get("/api/invoices", tags=["Invoices"])
def list_invoices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all invoices, newest first."""
    invoices = (
        db.query(Invoice)
        .order_by(Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_invoice_summary(inv) for inv in invoices]


@app.get("/api/invoices/{invoice_id}", tags=["Invoices"])
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Full invoice detail including all line items."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    return {
        **_invoice_summary(inv),
        "payment_terms": inv.payment_terms,
        "vendor_address": inv.vendor_address,
        "vendor_email": inv.vendor_email,
        "vendor_phone": inv.vendor_phone,
        "vendor_tax_id": inv.vendor_tax_id,
        "bill_to_address": inv.bill_to_address,
        "subtotal": _float(inv.subtotal),
        "tax_rate": _float(inv.tax_rate),
        "tax_amount": _float(inv.tax_amount),
        "discount_amount": _float(inv.discount_amount),
        "notes": inv.notes,
        "line_items": [
            {
                "id": li.id,
                "description": li.description,
                "item_code": li.item_code,
                "quantity": _float(li.quantity),
                "unit_of_measure": li.unit_of_measure,
                "unit_price": _float(li.unit_price),
                "total_price": _float(li.total_price),
            }
            for li in inv.line_items
        ],
    }


@app.delete("/api/invoices/{invoice_id}", tags=["Invoices"])
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    db.delete(inv)
    db.commit()
    return {"success": True, "deleted_id": invoice_id}


@app.get("/api/stats", tags=["System"])
def get_stats(db: Session = Depends(get_db)):
    total_invoices = db.query(Invoice).count()
    total_value = db.query(func.sum(Invoice.total_amount)).scalar() or 0
    total_line_items = db.query(LineItem).count()
    avg_value = db.query(func.avg(Invoice.total_amount)).scalar() or 0
    unique_vendors = db.query(func.count(func.distinct(Invoice.vendor_name))).scalar() or 0

    return {
        "total_invoices": total_invoices,
        "total_value": _float(total_value),
        "average_invoice_value": _float(avg_value),
        "total_line_items": total_line_items,
        "unique_vendors": unique_vendors,
    }
