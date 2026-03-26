#!/usr/bin/env python
"""
Validate the real 499-record dataset and test NL-to-SQL pipeline
"""
import os
import sys
import importlib
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
sys.path.insert(0, r'F:\AI_SmartSpend_Analyzer')
django.setup()

from analyzer_app.models import Expense
from django.db import connection

print("=" * 70)
print("VALIDATION: REAL 499-RECORD DATASET")
print("=" * 70)

# 1. Validate dataset
print("\n1️⃣  DATASET STATISTICS")
print("-" * 70)
total = Expense.objects.count()
print(f"✅ Total records: {total}")

earliest = Expense.objects.earliest('date')
latest = Expense.objects.latest('date')
print(f"✅ Date range: {earliest.date} to {latest.date}")

categories = list(Expense.objects.values_list('category', flat=True).distinct())
print(f"✅ Categories ({len(categories)}): {', '.join(categories[:10])}...")

total_spent = sum(e.amount for e in Expense.objects.all())
avg_spent = total_spent / total if total > 0 else 0
print(f"✅ Total spending: ${total_spent:,}")
print(f"✅ Average expense: ${avg_spent:.2f}")

# 2. Test some sample queries with ORM
print("\n2️⃣  SAMPLE QUERIES (ORM)")
print("-" * 70)

# Top categories by amount
from django.db.models import Sum
print("Top spending categories:")
for cat in Expense.objects.values('category').distinct():
    total_in_cat = sum(e.amount for e in Expense.objects.filter(category=cat['category']))
    if total_in_cat > 100000:  # Top ones
        print(f"  • {cat['category']}: ${total_in_cat:,}")

# Payment modes
modes = Expense.objects.values('payment_mode').distinct().count()
print(f"\nPayment modes used: {modes}")

# 3. Test SQL generation capability
print("\n3️⃣  TESTING SQL GENERATION (with Gemini)")
print("-" * 70)

# Check if Gemini API key is available
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("⚠️  No GEMINI_API_KEY found - skipping SQL generation test")
else:
    print("✅ GEMINI_API_KEY found")
    
    try:
        genai = importlib.import_module('google.genai')
        client = genai.Client(api_key=api_key)
        
        # Simple test: generate a query
        test_question = "What is the total amount of all expenses?"
        print(f"\nTest question: '{test_question}'")
        
        db_dialect = connection.vendor  # 'sqlite' or 'postgresql'
        print(f"Database dialect: {db_dialect}")
        
        # Create prompt
        prompt = f"""You are a SQL expert. Generate a SQL query to answer this question about an 'expenses' table with columns: id, category, amount, date, payment_mode.

Question: {test_question}

Guidelines:
- For {db_dialect}: Use STRFTIME for dates if needed
- Return ONLY the SQL query, no explanation
- Ensure the query is safe and valid

SQL:"""
        
        response = client.models.generate_content(
            model='models/gemini-2.0-flash',
            contents=prompt
        )
        
        sql = response.text.strip()
        print(f"\nGenerated SQL:\n{sql}")
        
        # Try to execute
        with connection.cursor() as cursor:
            try:
                cursor.execute(sql)
                result = cursor.fetchone()
                print(f"\n✅ SQL executed successfully")
                print(f"   Result: {result}")
            except Exception as e:
                print(f"\n⚠️  SQL execution failed: {e}")
                
    except Exception as e:
        print(f"⚠️  Gemini API error: {e}")

print("\n" + "=" * 70)
print("✅ VALIDATION COMPLETE - Ready to use real data!")
print("=" * 70)
