#!/usr/bin/env python
"""
Load 500-record expense dataset from Excel file with proper date handling.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
sys.path.insert(0, r'F:\AI_SmartSpend_Analyzer')
django.setup()

import pandas as pd
from datetime import datetime
from analyzer_app.models import Expense

# Read Excel file
excel_path = r'F:\AI_SmartSpend_Analyzer\expense_records_500.xlsx'
df = pd.read_excel(excel_path)

print(f"Loaded {len(df)} records from Excel")
print(f"First few rows (raw):")
print(df.head())
print(f"\nData types:\n{df.dtypes}")

# Clear existing records
print(f"\nClearing existing records...")
Expense.objects.all().delete()

# Parse dates more carefully
expenses = []
errors = []

for idx, row in df.iterrows():
    try:
        date_val = row.get('date')
        
        # Handle date parsing
        if pd.isna(date_val):
            parsed_date = None
        elif isinstance(date_val, str):
            # Try parsing "Jan 1", "Feb 14", etc. - treat as 2024
            try:
                parsed_date = datetime.strptime(date_val.strip(), '%b %d').replace(year=2024).date()
            except:
                # If that fails, try other formats
                try:
                    parsed_date = pd.to_datetime(date_val).date()
                except:
                    parsed_date = None
        else:
            # It's likely a datetime object already
            parsed_date = pd.to_datetime(date_val).date()
        
        # Skip leap year edge cases
        if date_val == 'Feb 29':
            errors.append(f"Row {idx}: Invalid leap year date (Feb 29)")
            continue
            
        expense = Expense(
            category=str(row.get('category', 'Uncategorized')).strip(),
            amount=int(float(row.get('amount', 0))),
            date=parsed_date,
            payment_mode=str(row.get('payment_mode', 'Unknown')).strip()
        )
        expenses.append(expense)
    except Exception as e:
        errors.append(f"Row {idx}: {e}")

if errors:
    print(f"\nEncountered {len(errors)} errors/skipped:")
    for err in errors[:10]:
        print(f"  {err}")

# Bulk insert
if expenses:
    Expense.objects.bulk_create(expenses, batch_size=100)
    print(f"\nSuccessfully inserted {len(expenses)} records")
else:
    print("No records to insert")

# Verify
final_count = Expense.objects.count()
print(f"\nFinal record count in database: {final_count}")

# Show sample with proper dates
print(f"\nSample records from database:")
for exp in Expense.objects.all()[:5]:
    print(f"  {exp.date} | {exp.category:15} | ${exp.amount:7} | {exp.payment_mode}")

# Statistics
print(f"\nDataset Statistics:")
print(f"  Total records: {Expense.objects.count()}")
if Expense.objects.exists():
    earliest = Expense.objects.earliest('date').date
    latest = Expense.objects.latest('date').date
    print(f"  Date range: {earliest} to {latest}")
    categories = Expense.objects.values('category').distinct().count()
    print(f"  Unique categories: {categories}")
    total_spent = sum(e.amount for e in Expense.objects.all())
    print(f"  Total amount: ${total_spent:,}")
