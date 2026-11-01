from decimal import Decimal
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from accounting.models import ChartOfAccount, JournalEntryLine
from api.permissions import require_roles


class TrialBalanceView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        accounts = ChartOfAccount.all_objects.filter(tenant=request.user.tenant).order_by("code")
        data = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for acc in accounts:
            lines = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc)
            debit = lines.aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
            credit = lines.aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
            
            # Only show accounts with activity
            if debit > 0 or credit > 0:
                data.append({
                    "code": acc.code,
                    "name": acc.name,
                    "type": acc.type,
                    "debit": debit,
                    "credit": credit
                })
                total_debit += debit
                total_credit += credit

        return Response({
            "accounts": data,
            "total_debit": total_debit,
            "total_credit": total_credit
        })


class ProfitLossView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        # Fetch Revenue Accounts (4xxx)
        revenue_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="4")
        # Fetch Expense Accounts (5xxx)
        expense_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="5")

        revenues = []
        expenses = []
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")

        for acc in revenue_accs:
            credit = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc).aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
            if credit > 0:
                revenues.append({"name": acc.name, "amount": credit})
                total_revenue += credit

        for acc in expense_accs:
            debit = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc).aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
            if debit > 0:
                expenses.append({"name": acc.name, "amount": debit})
                total_expense += debit

        return Response({
            "revenues": revenues,
            "expenses": expenses,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_profit": total_revenue - total_expense
        })


class BalanceSheetView(APIView):
    permission_classes = [require_roles("admin", "accountant", "finance_manager")]

    def get(self, request):
        # Assets (1xxx)
        asset_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="1")
        # Liabilities (2xxx)
        liab_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="2")
        # Equity (3xxx)
        equity_accs = ChartOfAccount.all_objects.filter(tenant=request.user.tenant, code__startswith="3")

        def calculate_balance(accounts, is_asset=False):
            items = []
            total = Decimal("0.00")
            for acc in accounts:
                lines = JournalEntryLine.all_objects.filter(tenant=request.user.tenant, account=acc)
                debit = lines.aggregate(s=Sum("debit"))["s"] or Decimal("0.00")
                credit = lines.aggregate(s=Sum("credit"))["s"] or Decimal("0.00")
                
                balance = (debit - credit) if is_asset else (credit - debit)
                
                if balance != 0:
                    items.append({"name": acc.name, "balance": balance})
                    total += balance
            return items, total

        assets, total_assets = calculate_balance(asset_accs, is_asset=True)
        liabilities, total_liab = calculate_balance(liab_accs, is_asset=False)
        equity, total_equity = calculate_balance(equity_accs, is_asset=False)

        # Note: This is a simplified Balance Sheet. Real IFRS would include retained earnings (Net Profit).
        return Response({
            "assets": assets,
            "total_assets": total_assets,
            "liabilities": liabilities,
            "total_liabilities": total_liab,
            "equity": equity,
            "total_equity": total_equity,
            "liabilities_and_equity": total_liab + total_equity
        })