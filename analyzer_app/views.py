import csv
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Sum
from django.db.utils import DatabaseError
from django.http import HttpResponseBadRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BudgetForm, ImportExpensesForm, QueryForm, SaveQueryForm
from .forecasting import detect_anomalies, forecast_next_month
from .models import Budget, Expense, QueryHistory, SavedQuery
from .utils import (
    build_budget_optimization_plan,
    build_conversation_followups,
    build_proactive_insight_feed,
    build_query_context_snapshot,
    build_detailed_answer,
    build_smart_insight,
    calculate_query_confidence,
    detect_recurring_transactions,
    execute_query,
    generate_sql_from_question,
    get_dashboard_stats,
    get_match_breakdown,
    is_no_data_result,
    needs_clarification,
    prepare_chart_data,
    resolve_followup_question,
)


QUERY_SUGGESTIONS = [
    'Total spending this month',
    'Highest spending category',
    'Average transaction amount',
    'Food expenses in January',
    'UPI transactions in March',
]


def _serialize_cell(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _get_default_user():
    user, _ = User.objects.get_or_create(username='local_profile')
    return user


def _build_budget_alerts(user):
    alerts = []
    budgets = Budget.objects.filter(user=user)
    for budget in budgets:
        spent = Expense.objects.filter(
            category__iexact=budget.category,
            date__year=datetime.now().year,
            date__month=datetime.now().month,
        ).aggregate(total=Sum('amount'))['total'] or 0

        pct = (spent * 100.0 / budget.monthly_limit) if budget.monthly_limit else 0
        if pct >= 100:
            level = 'danger'
            message = f"{budget.category}: Budget exceeded ({pct:.1f}%)."
        elif pct >= 80:
            level = 'warning'
            message = f"{budget.category}: You are at {pct:.1f}% of monthly budget."
        else:
            level = 'ok'
            message = f"{budget.category}: {pct:.1f}% used."
        alerts.append({'category': budget.category, 'spent': spent, 'limit': budget.monthly_limit, 'pct': round(pct, 2), 'level': level, 'message': message})
    return alerts


def _store_export_payload(request, question: str, columns, rows):
    request.session['latest_export_payload'] = {
        'question': question,
        'columns': [str(col) for col in columns],
        'rows': [[_serialize_cell(cell) for cell in row] for row in rows],
    }


def download_results_csv(request):
    payload = request.session.get('latest_export_payload')
    if not payload:
        response = HttpResponse('No data available for export. Run a query first.', content_type='text/plain')
        response.status_code = 400
        return response

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'ledgerlens_results_{timestamp}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Question', payload.get('question', '')])
    writer.writerow([])
    writer.writerow(payload.get('columns', []))
    writer.writerows(payload.get('rows', []))
    return response


def import_expenses(request):
    user = _get_default_user()
    form = ImportExpensesForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        file_obj = form.cleaned_data['file']
        filename = file_obj.name.lower()

        try:
            if filename.endswith('.csv'):
                content = file_obj.read().decode('utf-8', errors='ignore').splitlines()
                reader = csv.DictReader(content)
                rows = list(reader)
            elif filename.endswith('.xlsx'):
                import pandas as pd
                df = pd.read_excel(file_obj)
                rows = df.to_dict(orient='records')
            else:
                return render(request, 'import_expenses.html', {'form': form, 'error': 'Only CSV and XLSX files are supported.'})

            created = 0
            for row in rows:
                category = str(row.get('category', '')).strip()
                amount = row.get('amount', 0)
                date_value = row.get('date')
                payment_mode = str(row.get('payment_mode', '')).strip()
                if not category or not payment_mode:
                    continue

                try:
                    amount_int = int(float(amount))
                    if hasattr(date_value, 'date'):
                        parsed_date = date_value.date()
                    else:
                        parsed_date = datetime.strptime(str(date_value).strip(), '%Y-%m-%d').date()
                except Exception:
                    continue

                Expense.objects.create(
                    user=user,
                    category=category,
                    amount=amount_int,
                    date=parsed_date,
                    payment_mode=payment_mode,
                )
                created += 1

            messages.success(request, f'Successfully imported {created} records.')
            return redirect('index')
        except Exception as exc:
            return render(request, 'import_expenses.html', {'form': form, 'error': f'Import failed: {exc}'})

    return render(request, 'import_expenses.html', {'form': form})


def save_query(request):
    user = _get_default_user()
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')

    form = SaveQueryForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest('Invalid query data')

    SavedQuery.objects.create(
        user=user,
        title=form.cleaned_data['title'],
        question=form.cleaned_data['question'],
    )
    return redirect('index')


def delete_saved_query(request, saved_query_id):
    user = _get_default_user()
    query = get_object_or_404(SavedQuery, id=saved_query_id, user=user)
    query.delete()
    return redirect('index')


def manage_budgets(request):
    user = _get_default_user()
    form = BudgetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        Budget.objects.update_or_create(
            user=user,
            category=form.cleaned_data['category'],
            defaults={'monthly_limit': form.cleaned_data['monthly_limit']},
        )
        return redirect('manage_budgets')

    budgets = Budget.objects.filter(user=user)
    return render(request, 'budgets.html', {'form': form, 'budgets': budgets})

def index(request):
    user = _get_default_user()
    form = QueryForm(request.POST or None)

    user_expenses = Expense.objects.all()
    dashboard_stats = get_dashboard_stats(user_expenses)
    chart_data = prepare_chart_data(dashboard_stats)
    budget_alerts = _build_budget_alerts(user)
    forecast_info = forecast_next_month(user_expenses)
    anomalies = detect_anomalies(user_expenses)
    recurring_transactions = detect_recurring_transactions(
        list(user_expenses.values('category', 'payment_mode', 'amount', 'date'))
    )
    budget_optimization = build_budget_optimization_plan(
        stats=dashboard_stats,
        budget_alerts=budget_alerts,
        target_saving=5000,
    )
    history_items = list(QueryHistory.objects.filter(user=user)[:20])
    conversation_turns = request.session.get('conversation_turns', [])[-8:]
    ai_followup_suggestions = build_conversation_followups(request.session.get('last_query_context', {}))
    ai_feed_insights = build_proactive_insight_feed(
        stats=dashboard_stats,
        budget_alerts=budget_alerts,
        forecast_info=forecast_info,
        anomalies=anomalies,
        query_history=history_items,
    )

    context = {
        'form': form,
        'save_query_form': SaveQueryForm(),
        'query_suggestions': QUERY_SUGGESTIONS,
        'user_question': '',
        'generated_sql': '',
        'detailed_answer': '',
        'result_columns': [],
        'result_rows': [],
        'warning_message': '',
        'confidence_score': 0,
        'smart_insight': {},
        'ai_feed_insights': ai_feed_insights,
        'recurring_transactions': recurring_transactions,
        'budget_optimization': budget_optimization,
        'conversation_turns': conversation_turns,
        'ai_followup_suggestions': ai_followup_suggestions,
        'matched_record_count': 0,
        'matched_category_columns': [],
        'matched_category_rows': [],
        'matched_record_columns': [],
        'matched_record_rows': [],
        'matched_rows_truncated': False,
        'error_message': '',
        'clarification_message': '',
        'clarification_options': [],
        'conversation_note': '',
        'dashboard_stats': dashboard_stats,
        'chart_data': chart_data,
        'saved_queries': SavedQuery.objects.filter(user=user)[:12],
        'query_history': history_items[:12],
        'budget_alerts': budget_alerts,
        'forecast_info': forecast_info,
        'anomalies': anomalies,
    }

    if request.method == 'POST' and form.is_valid():
        question = form.cleaned_data['question'].strip()
        context['user_question'] = question

        previous_context = request.session.get('last_query_context', {})
        resolved_question, conversation_note = resolve_followup_question(question, previous_context)
        context['conversation_note'] = conversation_note

        clarification = needs_clarification(
            question=resolved_question,
            has_session_context=bool(previous_context),
        )
        if clarification.get('required'):
            context['clarification_message'] = clarification.get('message', '')
            context['clarification_options'] = clarification.get('options', [])
            context['detailed_answer'] = 'I paused execution until the question is clarified to avoid misleading results.'
            return render(request, 'index.html', context)

        context['user_question'] = resolved_question

        try:
            generated_sql = generate_sql_from_question(
                question=resolved_question,
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL,
                db_vendor=connection.vendor,
            )
            context['generated_sql'] = generated_sql

            columns, rows = execute_query(generated_sql)
            context['result_columns'] = columns
            context['result_rows'] = rows

            match_breakdown = get_match_breakdown(generated_sql)
            context['matched_record_count'] = match_breakdown['matched_count']
            context['matched_category_columns'] = match_breakdown['category_columns']
            context['matched_category_rows'] = match_breakdown['category_rows']
            context['matched_record_columns'] = match_breakdown['matched_columns']
            context['matched_record_rows'] = match_breakdown['matched_rows']
            context['matched_rows_truncated'] = match_breakdown['rows_truncated']

            context['detailed_answer'] = build_detailed_answer(
                resolved_question,
                columns,
                rows,
                match_breakdown,
            )

            context['smart_insight'] = build_smart_insight(
                match_breakdown=match_breakdown,
                overall_total_spent=dashboard_stats['total_spent'],
            )
            context['confidence_score'] = calculate_query_confidence(
                question=resolved_question,
                sql_query=generated_sql,
                match_breakdown=match_breakdown,
                rows=rows,
            )

            if is_no_data_result(rows) or match_breakdown['matched_count'] == 0:
                context['warning_message'] = 'No data found for this query. Try a different category or timeframe.'

            QueryHistory.objects.create(
                user=user,
                question=resolved_question,
                generated_sql=generated_sql,
                confidence_score=context['confidence_score'],
            )

            request.session['last_query_context'] = build_query_context_snapshot(resolved_question)
            turns = request.session.get('conversation_turns', [])
            turns.append({
                'user': question,
                'assistant': resolved_question,
                'confidence': context['confidence_score'],
            })
            request.session['conversation_turns'] = turns[-12:]
            context['conversation_turns'] = request.session['conversation_turns'][-8:]
            context['ai_followup_suggestions'] = build_conversation_followups(request.session['last_query_context'])
            _store_export_payload(request, resolved_question, columns, rows)
        except (ValueError, DatabaseError) as exc:
            context['error_message'] = str(exc)
        except Exception as exc:
            if settings.DEBUG:
                context['error_message'] = f'Unexpected error: {exc}'
            else:
                context['error_message'] = (
                    'Something went wrong while processing your request. '
                    'Check network connectivity, Gemini key, and database settings.'
                )

    return render(request, 'index.html', context)


def legacy_login_redirect(request):
    return redirect('index')
