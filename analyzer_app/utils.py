import re
from datetime import date, timedelta

import google.generativeai as genai
from django.db import connection


MODEL_FALLBACKS = [
    'models/gemini-2.0-flash',
    'models/gemini-2.5-flash',
    'models/gemini-flash-latest',
    'models/gemini-pro-latest',
]

MONTH_MAP = {
    'january': 1,
    'february': 2,
    'march': 3,
    'april': 4,
    'may': 5,
    'june': 6,
    'july': 7,
    'august': 8,
    'september': 9,
    'october': 10,
    'november': 11,
    'december': 12,
}

PAYMENT_MODE_HINTS = [
    'upi',
    'credit card',
    'debit card',
    'card',
    'wallet',
    'cash',
    'cheque',
    'net banking',
    'neft',
]

FOLLOW_UP_HINTS = [
    'those',
    'that',
    'same',
    'instead',
    'among them',
    'from that',
    'again',
]

INTENT_KEYWORDS = {
    'total': ['total', 'sum', 'spend', 'spending', 'expense'],
    'average': ['average', 'avg', 'mean'],
    'count': ['count', 'number of', 'transactions', 'how many'],
    'top': ['highest', 'top', 'largest', 'max'],
    'list': ['show', 'list', 'records'],
}


def normalize_model_name(model_name: str) -> str:
    if model_name.startswith('models/'):
        return model_name
    return f'models/{model_name}'


def extract_sql(text: str) -> str:
    """Extract SQL from markdown fences or plain text responses."""
    sql_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    sql = sql_match.group(1).strip() if sql_match else text.strip()
    return sql.rstrip(';')


def is_safe_query(sql: str) -> bool:
    """Allow only read-only SELECT queries against the expenses table."""
    lower_sql = sql.strip().lower()
    if not lower_sql.startswith('select'):
        return False

    blocked_keywords = ['insert', 'update', 'delete', 'drop', 'alter', 'truncate', 'create']
    if any(keyword in lower_sql for keyword in blocked_keywords):
        return False

    # Check that 'expenses' table is referenced somewhere (in FROM, JOIN, or subquery)
    # More flexible pattern to handle various SQL syntax styles (backticks, quotes, no quotes)
    table_patterns = [
        r"\bexpenses\b",  # Plain reference
        r"`expenses`",    # Backticks
        r'"expenses"',    # Double quotes
        r"'expenses'",    # Single quotes
    ]
    return any(re.search(pattern, lower_sql) for pattern in table_patterns)


def _escape_like_value(text: str) -> str:
    return text.replace("'", "''")


def _detect_month(question_lower: str):
    for month_name, month_num in MONTH_MAP.items():
        if month_name in question_lower:
            return month_num
    return None


def _detect_payment_mode(question_lower: str):
    for mode in PAYMENT_MODE_HINTS:
        if mode in question_lower:
            return mode
    return None


def _detect_category(question_lower: str):
    """Find a category mentioned in question from existing database values."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT category FROM expenses')
            categories = [row[0] for row in cursor.fetchall() if row and row[0]]
    except Exception:
        categories = []

    for category in categories:
        if str(category).lower() in question_lower:
            return str(category)

    # Common fallback category words.
    common_categories = [
        'food',
        'dining',
        'groceries',
        'shopping',
        'travel',
        'transport',
        'entertainment',
        'medical',
        'gym',
        'hotel',
        'internet',
    ]
    for cat in common_categories:
        if cat in question_lower:
            return cat
    return None


def _month_name_from_number(month_num: int) -> str:
    for month_name, value in MONTH_MAP.items():
        if value == month_num:
            return month_name.capitalize()
    return ''


def extract_question_filters(question: str) -> dict:
    question_lower = question.lower()
    month_num = _detect_month(question_lower)
    payment_mode = _detect_payment_mode(question_lower)
    category = _detect_category(question_lower)
    return {
        'month_num': month_num,
        'month_name': _month_name_from_number(month_num) if month_num else '',
        'payment_mode': payment_mode or '',
        'category': category or '',
    }


def detect_question_intent(question: str) -> str:
    question_lower = question.lower()
    for intent, tokens in INTENT_KEYWORDS.items():
        if any(token in question_lower for token in tokens):
            return intent
    return ''


def resolve_followup_question(question: str, session_context: dict) -> tuple[str, str]:
    """Rewrite follow-up questions using previous filter context when needed."""
    if not session_context:
        return question, ''

    question_lower = question.lower()
    is_followup = any(token in question_lower for token in FOLLOW_UP_HINTS)
    if not is_followup:
        return question, ''

    current_filters = extract_question_filters(question)
    previous_filters = session_context.get('filters', {})
    merged_filters = {
        'month_name': current_filters.get('month_name') or previous_filters.get('month_name', ''),
        'payment_mode': current_filters.get('payment_mode') or previous_filters.get('payment_mode', ''),
        'category': current_filters.get('category') or previous_filters.get('category', ''),
    }

    current_intent = detect_question_intent(question)
    previous_intent = session_context.get('intent', '')
    merged_intent = current_intent or previous_intent or 'total'

    intent_phrase = {
        'total': 'total spending',
        'average': 'average transaction amount',
        'count': 'number of transactions',
        'top': 'highest spending category',
        'list': 'expense records',
    }.get(merged_intent, 'total spending')

    rebuilt = f'Show me {intent_phrase}'
    if merged_filters['category']:
        rebuilt += f" for {merged_filters['category']}"
    if merged_filters['payment_mode']:
        rebuilt += f" using {merged_filters['payment_mode']}"
    if merged_filters['month_name']:
        rebuilt += f" in {merged_filters['month_name']}"

    if rebuilt.strip().lower() == question.strip().lower():
        return question, ''

    note = 'Follow-up interpreted using your previous query context.'
    return rebuilt, note


def needs_clarification(question: str, has_session_context: bool) -> dict:
    """Return clarification prompt when the question is likely ambiguous."""
    question_lower = question.lower().strip()
    intent = detect_question_intent(question)
    filters = extract_question_filters(question)

    reference_tokens = ['that', 'those', 'same', 'again', 'it']
    has_reference = any(token in question_lower for token in reference_tokens)
    if has_reference and not has_session_context:
        return {
            'required': True,
            'message': 'This looks like a follow-up question, but there is no prior query context yet.',
            'options': [
                'Show me total spending this month',
                'Show me highest spending category this month',
                'Show me all expense records for this month',
            ],
        }

    has_any_filter = bool(filters.get('month_name') or filters.get('category') or filters.get('payment_mode'))
    word_count = len([w for w in question_lower.split() if w])
    if not intent and not has_any_filter and word_count <= 6:
        return {
            'required': True,
            'message': 'Please clarify what kind of answer you want so I can generate the right SQL.',
            'options': [
                'Show me total spending this month',
                'Show me average transaction amount this month',
                'Show me number of transactions this month',
                'Show me highest spending category this month',
            ],
        }

    return {'required': False, 'message': '', 'options': []}


def build_query_context_snapshot(question: str) -> dict:
    return {
        'filters': extract_question_filters(question),
        'intent': detect_question_intent(question),
        'question': question,
    }


def build_proactive_insight_feed(stats: dict, budget_alerts: list, forecast_info: dict, anomalies: list, query_history: list) -> list:
    insights = []

    categories = stats.get('categories', [])
    total_spent = float(stats.get('total_spent') or 0)
    if categories and total_spent > 0:
        top_cat = categories[0]
        top_total = float(top_cat.get('total_amount') or 0)
        top_pct = (top_total * 100.0 / total_spent) if total_spent else 0
        insights.append({
            'title': 'Largest Spend Driver',
            'text': f"{top_cat.get('category', 'Unknown')} contributes {top_pct:.1f}% of your total spend.",
            'suggestion': 'Set a category-specific budget to control this concentration risk.',
            'tone': 'focus',
        })

    trend = str(forecast_info.get('trend') or '').lower()
    forecast_value = float(forecast_info.get('next_month_forecast') or 0)
    if trend in ['up', 'rising', 'increase'] and forecast_value > 0:
        insights.append({
            'title': 'Upcoming Month Signal',
            'text': f'Forecast suggests around {int(forecast_value)} in next month with an upward trend.',
            'suggestion': 'Review discretionary categories now to avoid next-month overspend.',
            'tone': 'warning',
        })

    danger_alerts = [alert for alert in budget_alerts if alert.get('level') in ['danger', 'warning']]
    if danger_alerts:
        top_alert = sorted(danger_alerts, key=lambda item: item.get('pct', 0), reverse=True)[0]
        insights.append({
            'title': 'Budget Risk',
            'text': f"{top_alert.get('category', 'Category')} is at {top_alert.get('pct', 0)}% of monthly budget.",
            'suggestion': 'Ask: "Show me recent transactions for this category" to find optimization opportunities.',
            'tone': 'warning',
        })

    if anomalies:
        insights.append({
            'title': 'Unusual Transactions Found',
            'text': f'{len(anomalies)} potential anomalies were detected in your latest data window.',
            'suggestion': 'Inspect these records and tag expected outliers for cleaner forecasting.',
            'tone': 'focus',
        })

    if query_history:
        latest = query_history[0]
        latest_question = getattr(latest, 'question', '')
        if latest_question:
            insights.append({
                'title': 'Suggested Follow-Up',
                'text': f'Based on your recent query: "{latest_question[:80]}"',
                'suggestion': 'Try adding a payment mode or month filter to get a sharper insight.',
                'tone': 'neutral',
            })

    return insights[:4]


def detect_recurring_transactions(expense_records: list) -> list:
    """Detect likely recurring expenses by stable amount/category/payment over multiple months."""
    grouped = {}
    for row in expense_records:
        category = str(row.get('category') or '').strip()
        payment_mode = str(row.get('payment_mode') or '').strip()
        amount = row.get('amount')
        expense_date = row.get('date')

        if not category or not payment_mode or amount is None or not expense_date:
            continue

        try:
            amount_val = int(float(amount))
            month_key = f'{expense_date.year:04d}-{expense_date.month:02d}'
        except Exception:
            continue

        key = (category.lower(), payment_mode.lower(), amount_val)
        if key not in grouped:
            grouped[key] = {
                'category': category,
                'payment_mode': payment_mode,
                'amount': amount_val,
                'months': set(),
                'count': 0,
            }

        grouped[key]['months'].add(month_key)
        grouped[key]['count'] += 1

    recurring = []
    for item in grouped.values():
        month_count = len(item['months'])
        if month_count >= 3 and item['count'] >= 3:
            recurring.append({
                'category': item['category'],
                'payment_mode': item['payment_mode'],
                'amount': item['amount'],
                'months_seen': month_count,
                'occurrences': item['count'],
                'annual_estimate': item['amount'] * 12,
            })

    recurring.sort(key=lambda x: (x['annual_estimate'], x['occurrences']), reverse=True)
    return recurring[:8]


def build_budget_optimization_plan(stats: dict, budget_alerts: list, target_saving: int = 5000) -> dict:
    """Suggest category cuts to reach a monthly savings target."""
    categories = stats.get('categories', []) or []
    alert_map = {str(a.get('category', '')).lower(): a for a in budget_alerts}

    actions = []
    remaining = max(int(target_saving or 0), 0)
    projected_saving = 0

    for cat in categories[:6]:
        if remaining <= 0:
            break

        category = str(cat.get('category') or 'Other')
        total_amount = int(float(cat.get('total_amount') or 0))
        if total_amount <= 0:
            continue

        alert = alert_map.get(category.lower())
        if alert and alert.get('level') in ['danger', 'warning']:
            cut_pct = 15
        elif total_amount >= 10000:
            cut_pct = 12
        else:
            cut_pct = 8

        candidate_save = max(int(total_amount * cut_pct / 100), 1)
        suggested_cut = min(candidate_save, remaining)
        if suggested_cut <= 0:
            continue

        projected_saving += suggested_cut
        remaining -= suggested_cut

        actions.append({
            'category': category,
            'monthly_spend': total_amount,
            'suggested_cut': suggested_cut,
            'cut_pct': round((suggested_cut * 100.0) / total_amount, 1),
            'new_target': max(total_amount - suggested_cut, 0),
        })

    status = 'on-track' if projected_saving >= target_saving else 'partial'
    gap = max(target_saving - projected_saving, 0)
    return {
        'target_saving': target_saving,
        'projected_saving': projected_saving,
        'remaining_gap': gap,
        'status': status,
        'actions': actions,
        'summary': (
            f'Projected monthly saving is {projected_saving}. '
            + ('Target achieved.' if gap == 0 else f'Need {gap} more to reach target.')
        ),
    }


def build_conversation_followups(session_context: dict) -> list:
    """Build AI-style follow-up suggestions from current conversational context."""
    if not session_context:
        return [
            'Show me total spending this month',
            'Show me highest spending category this month',
            'Show me UPI transactions in March',
        ]

    filters = session_context.get('filters', {})
    category = filters.get('category', 'this category')
    month_name = filters.get('month_name', 'this month')
    payment_mode = filters.get('payment_mode', '').strip()

    prompts = [
        f'Show me average transaction amount for {category} in {month_name}',
        f'Show me number of transactions for {category} in {month_name}',
    ]

    if payment_mode:
        prompts.append(f'Show me total spending for {category} using {payment_mode} in {month_name}')
    else:
        prompts.append(f'Show me total spending for {category} using UPI in {month_name}')

    return prompts


def _build_filters_sql(question: str, db_vendor: str):
    question_lower = question.lower()
    where_parts = []

    month_num = _detect_month(question_lower)
    payment_mode = _detect_payment_mode(question_lower)
    category = _detect_category(question_lower)

    if month_num is not None:
        if db_vendor == 'postgresql':
            where_parts.append(f'EXTRACT(MONTH FROM date) = {int(month_num)}')
        else:
            where_parts.append(f"strftime('%m', date) = '{int(month_num):02d}'")

    if payment_mode:
        safe_mode = _escape_like_value(payment_mode)
        where_parts.append(f"lower(payment_mode) LIKE '%{safe_mode.lower()}%'")

    if category:
        safe_category = _escape_like_value(category)
        where_parts.append(f"lower(category) LIKE '%{safe_category.lower()}%'")

    if not where_parts:
        return ''
    return ' WHERE ' + ' AND '.join(where_parts)


def generate_sql_with_fallback(question: str, db_vendor: str) -> str:
    """Generate safe SQL from common question patterns when Gemini is unavailable."""
    question_lower = question.lower()
    where_sql = _build_filters_sql(question, db_vendor)

    if any(token in question_lower for token in ['highest spending category', 'top category', 'highest category']):
        return (
            'SELECT category, SUM(amount) AS total_amount '
            'FROM expenses'
            f'{where_sql} '
            'GROUP BY category '
            'ORDER BY total_amount DESC '
            'LIMIT 1'
        )

    if any(token in question_lower for token in ['average transaction', 'avg transaction', 'average expense', 'avg expense']):
        return f'SELECT AVG(amount) AS avg_amount FROM expenses{where_sql}'

    if any(token in question_lower for token in ['number of transactions', 'transactions', 'count']):
        return f'SELECT COUNT(*) AS transaction_count FROM expenses{where_sql}'

    if any(token in question_lower for token in ['total', 'spend', 'spending', 'expense']):
        return f'SELECT SUM(amount) AS total_amount FROM expenses{where_sql}'

    return (
        'SELECT id, category, amount, date, payment_mode '
        'FROM expenses'
        f'{where_sql} '
        'ORDER BY date DESC, id DESC '
        'LIMIT 50'
    )


def build_gemini_prompt(question: str, dialect: str) -> str:
    """Build a filter-aware prompt for NL-to-SQL conversion."""
    month_hint = (
        "For month filters in SQLite use strftime('%m', date) and map January=01, February=02, etc. "
        "For PostgreSQL use EXTRACT(MONTH FROM date)."
    )

    return f"""
You are an expert SQL query generator.
Convert the user question into a single SQL SELECT query.

Target SQL dialect: {dialect}

Database schema:
Table: expenses
Columns:
- id (integer primary key)
- category (text)
- amount (integer)
- date (date)
- payment_mode (text)

Rules:
- Return only SQL. No explanation.
- Generate read-only SQL using SELECT only.
- Use valid {dialect} syntax.
- Do not reference any table other than expenses.
- Support filters by category, month, and payment_mode.
- For text filters (category/payment_mode), use case-insensitive matching.
- If the user asks for highest/lowest/top category, use GROUP BY category and ORDER BY aggregate.
- If the user asks total spending for any filter, use SUM(amount).
- If the user asks number of transactions, use COUNT(*).
- {month_hint}

Examples:
- "Food expenses in January" -> SELECT ... FROM expenses WHERE lower(category) LIKE '%food%' AND ...month filter...
- "UPI transactions in March" -> SELECT ... WHERE lower(payment_mode) LIKE '%upi%' AND ...month filter...

User question:
{question}
"""


def generate_sql_from_question(question: str, api_key: str, model_name: str, db_vendor: str) -> str:
    if not api_key:
        raise ValueError('Gemini API key is missing. Add GEMINI_API_KEY in your .env file.')

    dialect = 'PostgreSQL' if db_vendor == 'postgresql' else 'SQLite'
    prompt = build_gemini_prompt(question, dialect)


    genai.configure(api_key=api_key)

    configured_model = normalize_model_name(model_name)
    candidate_models = [configured_model] + [m for m in MODEL_FALLBACKS if m != configured_model]
    response = None
    last_exception = None

    for candidate in candidate_models:
        try:
            model = genai.GenerativeModel(candidate)
            response = model.generate_content(prompt)
            if response:
                break
        except Exception as exc:
            last_exception = exc
            continue

    if response is None:
        # Fallback for network/DNS/rate-limit or temporary Gemini failures.
        fallback_sql = generate_sql_with_fallback(question, db_vendor)
        if is_safe_query(fallback_sql):
            return fallback_sql

        if last_exception:
            error_text = str(last_exception).lower()
            if any(token in error_text for token in ['getaddrinfo', 'name resolution', 'dns', 'connection', 'timed out']):
                raise ValueError(
                    'Gemini is currently unreachable due to a network/DNS issue. '
                    'Please check internet connectivity and try again.'
                )
            raise ValueError(f'Gemini request failed: {last_exception}')
        raise ValueError('Gemini request failed with no response.')

    if not response or not getattr(response, 'text', None):
        raise ValueError('Gemini did not return a usable SQL response.')

    sql_query = extract_sql(response.text)
    if not is_safe_query(sql_query):
        raise ValueError('Generated SQL was unsafe or not valid for the expenses table.')

    return sql_query


def execute_query(sql_query: str):
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        columns = [column[0] for column in cursor.description] if cursor.description else []
        rows = cursor.fetchall() if cursor.description else []
    return columns, rows


def extract_where_clause(sql_query: str) -> str:
    """Extract WHERE clause body from a SELECT query, excluding GROUP/ORDER/LIMIT."""
    match = re.search(
        r"\bwhere\b\s*(.*?)(\bgroup\s+by\b|\border\s+by\b|\blimit\b|\boffset\b|$)",
        sql_query,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ''
    return match.group(1).strip()


def get_match_breakdown(sql_query: str):
    """Return matched record count, category breakdown, and matched rows preview."""
    where_clause = extract_where_clause(sql_query)
    base_query = 'FROM expenses'
    if where_clause:
        base_query += f' WHERE {where_clause}'

    count_sql = f'SELECT COUNT(*) AS matched_records {base_query}'
    category_sql = (
        'SELECT category, COUNT(*) AS record_count, COALESCE(SUM(amount), 0) AS total_amount '
        f'{base_query} '
        'GROUP BY category '
        'ORDER BY record_count DESC, category ASC'
    )
    matched_rows_sql = (
        'SELECT id, category, amount, date, payment_mode '
        f'{base_query} '
        'ORDER BY date ASC, id ASC '
        'LIMIT 50'
    )

    _, count_rows = execute_query(count_sql)
    category_columns, category_rows = execute_query(category_sql)
    matched_columns, matched_rows = execute_query(matched_rows_sql)

    matched_count = count_rows[0][0] if count_rows else 0
    category_names = [row[0] for row in category_rows if row and row[0]]
    matched_total_amount = sum(row[2] for row in category_rows) if category_rows else 0

    return {
        'matched_count': matched_count,
        'category_columns': category_columns,
        'category_rows': category_rows,
        'category_names': category_names,
        'matched_columns': matched_columns,
        'matched_rows': matched_rows,
        'rows_truncated': matched_count > len(matched_rows),
        'matched_total_amount': matched_total_amount,
    }


def is_no_data_result(rows) -> bool:
    """Treat empty rows and single-row all-None aggregates as no data."""
    if not rows:
        return True
    if len(rows) == 1 and all(cell is None for cell in rows[0]):
        return True
    return False


def build_detailed_answer(question: str, columns, rows, match_breakdown=None) -> str:
    """Create a user-friendly explanation from SQL output."""
    if is_no_data_result(rows):
        return 'No data found for this query. Try a different category or timeframe.'

    if len(columns) == 1 and len(rows) == 1:
        metric = columns[0]
        value = rows[0][0]
        if value is None:
            value = 0

        matched_count_text = ''
        categories_text = ''
        if match_breakdown:
            matched_count = match_breakdown.get('matched_count', 0)
            matched_count_text = f' Found {matched_count} matching records in your dataset.'
            category_names = match_breakdown.get('category_names', [])
            if category_names:
                categories_text = f" Matching categories: {', '.join(category_names)}."

        metric_lower = metric.lower()
        if 'sum' in metric_lower or 'total' in metric_lower:
            return (
                f"For your question \"{question}\", the total expense amount is {value}. "
                f"That means your matched spending adds up to {value} currency units."
                f"{matched_count_text}{categories_text}"
            )
        if 'count' in metric_lower:
            return (
                f"For your question \"{question}\", the result is {value}. "
                f"That means {value} expense records matched your filters."
                f"{categories_text}"
            )
        if 'avg' in metric_lower:
            return (
                f"For your question \"{question}\", the average expense is {value}. "
                f"That means the mean value across matched records is {value} currency units."
                f"{matched_count_text}{categories_text}"
            )

        return (
            f"For your question \"{question}\", {metric} is {value}. "
            f"This is the final value returned by the generated SQL query."
            f"{matched_count_text}{categories_text}"
        )

    row_count = len(rows)
    column_count = len(columns)
    return (
        f"Your query returned {row_count} rows across {column_count} columns. "
        'See the table below for the full breakdown.'
    )


def build_smart_insight(match_breakdown: dict, overall_total_spent: float) -> dict:
    matched_total = float(match_breakdown.get('matched_total_amount') or 0)
    matched_count = int(match_breakdown.get('matched_count') or 0)
    category_names = match_breakdown.get('category_names', [])
    category_label = ', '.join(category_names) if category_names else 'selected records'

    contribution_pct = 0.0
    if overall_total_spent:
        contribution_pct = (matched_total * 100.0) / float(overall_total_spent)

    if contribution_pct >= 30:
        suggestion = 'This category contributes heavily to your total spend. Consider setting a monthly cap.'
    elif contribution_pct >= 15:
        suggestion = 'This category is a moderate contributor. Watch it weekly to avoid overspending.'
    else:
        suggestion = 'Spending in this area is relatively controlled. Maintain this pattern for better savings.'

    return {
        'total_amount': matched_total,
        'transaction_count': matched_count,
        'contribution_pct': round(contribution_pct, 2),
        'insight_text': (
            f'You spent {int(matched_total)} on {category_label} across {matched_count} transactions, '
            f'contributing {round(contribution_pct, 2)}% of total spending.'
        ),
        'suggestion_text': suggestion,
    }


def calculate_query_confidence(question: str, sql_query: str, match_breakdown: dict, rows) -> int:
    """Simple heuristic confidence score for UI display."""
    score = 82
    lower_question = question.lower()
    lower_sql = sql_query.lower()

    # Reward alignment between question intent and SQL clauses.
    if any(token in lower_question for token in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']) and ('strftime' in lower_sql or 'extract(month' in lower_sql):
        score += 6
    if any(token in lower_question for token in ['upi', 'card', 'cash', 'wallet', 'neft', 'cheque']) and 'payment_mode' in lower_sql:
        score += 5
    if 'category' in lower_sql and any(token in lower_question for token in ['food', 'dining', 'shopping', 'travel', 'entertainment']):
        score += 4

    matched_count = match_breakdown.get('matched_count', 0)
    if matched_count > 0 and rows:
        score += 3
    if matched_count == 0 or is_no_data_result(rows):
        score -= 14

    if score < 55:
        return 55
    if score > 98:
        return 98
    return score


def get_dashboard_stats(expenses_qs):
    """Get overall spending statistics for dashboard."""
    from django.db.models import Sum, Count, Avg

    total_expenses = expenses_qs.aggregate(
        total=Sum('amount'),
        count=Count('id'),
        avg=Avg('amount'),
    )

    category_stats = expenses_qs.values('category').annotate(
        total_amount=Sum('amount'),
        count=Count('id'),
        avg_amount=Avg('amount'),
    ).order_by('-total_amount')

    monthly_stats = []
    if expenses_qs.exists():
        earliest_date = expenses_qs.earliest('date').date
        latest_date = expenses_qs.latest('date').date

        current = date(earliest_date.year, earliest_date.month, 1)
        while current <= latest_date:
            month_start = current
            if current.month == 12:
                month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)

            month_total = expenses_qs.filter(
                date__gte=month_start,
                date__lte=month_end,
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            month_count = expenses_qs.filter(
                date__gte=month_start,
                date__lte=month_end,
            ).aggregate(Count('id'))['id__count'] or 0

            monthly_stats.append({
                'month': month_start.strftime('%b %Y'),
                'total': month_total,
                'count': month_count,
            })

            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    return {
        'total_spent': total_expenses['total'] or 0,
        'total_transactions': total_expenses['count'] or 0,
        'avg_transaction': round(float(total_expenses['avg'] or 0), 2),
        'categories': list(category_stats),
        'monthly': monthly_stats,
    }


def prepare_chart_data(stats):
    category_labels = [cat['category'] for cat in stats['categories'][:10]]
    category_values = [cat['total_amount'] for cat in stats['categories'][:10]]
    monthly_labels = [m['month'] for m in stats['monthly']]
    monthly_values = [m['total'] for m in stats['monthly']]

    return {
        'category_chart': {
            'labels': category_labels,
            'data': category_values,
        },
        'monthly_chart': {
            'labels': monthly_labels,
            'data': monthly_values,
        },
    }
