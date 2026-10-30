from accounting.models import ChartOfAccount

def seed_default_coa(tenant):
    """Creates the standard Chart of Accounts for a tenant."""
    accounts = [
        # Assets
        ("1000", "Cash & Bank", "asset"),
        ("1100", "Accounts Receivable", "asset"),
        ("1200", "Inventory", "asset"),
        ("1500", "Fixed Assets", "asset"),
        # Liabilities
        ("2000", "Accounts Payable", "liability"),
        # Equity
        ("3000", "Owner's Equity", "equity"),
        # Revenue
        ("4000", "Consultation Revenue", "revenue"),
        ("4100", "Pharmacy Revenue", "revenue"),
        ("4200", "Lab Revenue", "revenue"),
        ("4300", "Radiology Revenue", "revenue"),
        # Expenses
        ("5000", "Salaries & Wages", "expense"),
        ("5100", "Rent Expense", "expense"),
        ("5200", "Utilities Expense", "expense"),
        ("5300", "Medical Supplies", "expense"),
    ]
    
    for code, name, type in accounts:
        ChartOfAccount.all_objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": name, "type": type}
        )
