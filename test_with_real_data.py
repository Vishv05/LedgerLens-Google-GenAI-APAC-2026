#!/usr/bin/env python
"""
Test the SmartSpend app with real 499-record dataset
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
sys.path.insert(0, r'F:\AI_SmartSpend_Analyzer')
django.setup()

from django.test import Client
import json

client = Client()

# Test queries
test_queries = [
    "What is my total spending on dining?",
    "How many food expenses did I have?",
    "What is my average expense amount?",
    "Which payment mode did I use the most?",
]

print("=" * 70)
print("TESTING SMARTSPEND WITH REAL 499-RECORD DATASET")
print("=" * 70)

for question in test_queries:
    print(f"\n📊 Query: '{question}'")
    print("-" * 70)
    
    response = client.post('/', {'question': question})
    
    if response.status_code == 200:
        # Extract relevant parts
        content = response.content.decode('utf-8')
        
        # Check for generated SQL
        if '<pre id="sql-block">' in content:
            sql_start = content.find('<pre id="sql-block">') + len('<pre id="sql-block">')
            sql_end = content.find('</pre>', sql_start)
            sql = content[sql_start:sql_end].strip()
            print(f"Generated SQL:\n  {sql[:100]}...")
        
        # Check for detailed answer
        if 'DETAILED_ANSWER=' in content:
            # Try to extract from response attributes
            if 'id="detailed-answer">' in content:
                ans_start = content.find('id="detailed-answer">') + len('id="detailed-answer">')
                ans_end = content.find('</div>', ans_start)
                answer = content[ans_start:ans_end].strip()
                print(f"Detailed Answer:\n  {answer[:120]}...")
        
        # Check for table results
        if '<table' in content and '<tbody>' in content:
            tbody_start = content.find('<tbody>')
            tbody_end = content.find('</tbody>', tbody_start)
            table = content[tbody_start+7:tbody_end]
            row_count = table.count('<tr>')
            print(f"Results: {row_count} rows returned")
        
        print(f"✅ Status: SUCCESS")
    else:
        print(f"❌ Status: {response.status_code}")

print("\n" + "=" * 70)
print("Testing dataset stats...")
from analyzer_app.models import Expense
print(f"✅ Total records in DB: {Expense.objects.count()}")
print(f"✅ Categories: {Expense.objects.values('category').distinct().count()}")
total = sum(e.amount for e in Expense.objects.all())
print(f"✅ Total spending: ${total:,}")
print("=" * 70)
