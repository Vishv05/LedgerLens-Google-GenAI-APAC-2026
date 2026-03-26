from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'amount', 'date', 'payment_mode')
    list_filter = ('category', 'payment_mode')
    search_fields = ('category', 'payment_mode')
