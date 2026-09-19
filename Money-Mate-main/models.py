"""MoneyMate data model."""


class Transaction:
    def __init__(self, transaction_type, amount, category, date, description="", item_id=""):
        self.id = item_id
        self.type = transaction_type
        self.amount = float(amount)
        self.category = category
        self.date = date
        self.description = description

    @property
    def signed_amount(self):
        return self.amount if self.type == "income" else -self.amount

    def describe(self):
        label = "รายรับ" if self.type == "income" else "รายจ่าย"
        return f"{label} {self.amount:,.2f} บาท · {self.category} · {self.date}"
