from collections import defaultdict
from datetime import date

from django.db.models import Sum


def monthly_totals(expenses_qs):
    points = []
    by_month = defaultdict(int)
    for expense in expenses_qs:
        key = (expense.date.year, expense.date.month)
        by_month[key] += int(expense.amount)

    for key in sorted(by_month.keys()):
        year, month = key
        points.append({'label': date(year, month, 1).strftime('%b %Y'), 'total': by_month[key]})
    return points


def forecast_next_month(expenses_qs):
    """Simple trend forecast using average month-over-month change."""
    points = monthly_totals(expenses_qs)
    if not points:
        return {'next_month_forecast': 0, 'trend': 'insufficient-data'}
    if len(points) == 1:
        return {'next_month_forecast': points[0]['total'], 'trend': 'flat'}

    deltas = []
    for idx in range(1, len(points)):
        deltas.append(points[idx]['total'] - points[idx - 1]['total'])

    avg_delta = sum(deltas) / len(deltas)
    forecast = max(0, int(points[-1]['total'] + avg_delta))

    if avg_delta > 0:
        trend = 'up'
    elif avg_delta < 0:
        trend = 'down'
    else:
        trend = 'flat'

    return {'next_month_forecast': forecast, 'trend': trend}


def detect_anomalies(expenses_qs):
    """Detect unusual daily spending spikes compared to average daily spend."""
    daily = expenses_qs.values('date').annotate(total=Sum('amount')).order_by('date')
    totals = [int(item['total'] or 0) for item in daily]
    if not totals:
        return []

    mean = sum(totals) / len(totals)
    variance = sum((x - mean) ** 2 for x in totals) / len(totals)
    std = variance ** 0.5
    threshold = mean + (2 * std)

    anomalies = []
    for item in daily:
        total = int(item['total'] or 0)
        if total > threshold:
            anomalies.append({'date': item['date'], 'total': total})

    return anomalies[:5]
