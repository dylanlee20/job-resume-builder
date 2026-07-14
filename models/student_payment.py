"""StudentPayment — a payment a student made, with the FX rate at pay time.

Admin-entered. This is the revenue side of the weekly reconciliation report.
Everything reconciles in USD, so each payment stores the exchange rate that was
in effect when the student paid (fx_to_usd) and the derived amount_usd.
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from models.database import db


class StudentPayment(db.Model):
    __tablename__ = "student_payments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    amount = db.Column(db.Numeric(10, 2), nullable=False)         # in `currency`
    currency = db.Column(db.String(3), nullable=False, default="CNY")
    # USD/CNY exchange rate: CNY per USD, e.g. 7.20. USD = amount / this rate.
    # (Column name is historical; it holds the USD/CNY per-USD rate. Use 1 for USD.)
    fx_to_usd = db.Column(db.Numeric(12, 6), nullable=False, default=1)
    amount_usd = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    paid_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("User", backref=db.backref("payments", lazy="dynamic"))

    def __repr__(self):
        return f"<StudentPayment student={self.student_id} {self.amount} {self.currency}>"

    def recompute_usd(self) -> None:
        # USD = local amount / (USD/CNY rate). USD payments use rate 1.
        rate = Decimal(self.fx_to_usd or 0)
        amt = (Decimal(self.amount or 0) / rate) if rate else Decimal(0)
        self.amount_usd = amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
