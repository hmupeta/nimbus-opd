from django.contrib import admin
from common.admin import TenantModelAdmin
from .models import ChartOfAccount, JournalEntry, JournalEntryLine


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(TenantModelAdmin):
    list_display = ("code", "name", "type", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("code", "name")


@admin.register(JournalEntry)
class JournalEntryAdmin(TenantModelAdmin):
    list_display = ("id", "date", "reference", "description")
    list_filter = ("date",)
    search_fields = ("reference", "description")
    inlines = [JournalEntryLineInline]
