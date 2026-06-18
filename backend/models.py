from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    # Identifiers
    invoice_number = Column(String(100))
    invoice_date = Column(Date)
    due_date = Column(Date)
    payment_terms = Column(String(100))

    # Vendor (sender)
    vendor_name = Column(String(255))
    vendor_address = Column(Text)
    vendor_email = Column(String(255))
    vendor_phone = Column(String(100))
    vendor_tax_id = Column(String(100))

    # Bill-to (buyer)
    bill_to_name = Column(String(255))
    bill_to_address = Column(Text)

    # Financials
    subtotal = Column(Numeric(14, 2))
    tax_rate = Column(Numeric(6, 4))
    tax_amount = Column(Numeric(14, 2))
    discount_amount = Column(Numeric(14, 2))
    total_amount = Column(Numeric(14, 2))
    currency = Column(String(10), default="USD")

    notes = Column(Text)
    pdf_filename = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())

    line_items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))

    description = Column(Text)
    item_code = Column(String(100))
    quantity = Column(Numeric(12, 3))
    unit_of_measure = Column(String(50))
    unit_price = Column(Numeric(14, 4))
    total_price = Column(Numeric(14, 2))

    invoice = relationship("Invoice", back_populates="line_items")
