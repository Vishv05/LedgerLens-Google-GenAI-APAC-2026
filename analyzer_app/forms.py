from django import forms


class QueryForm(forms.Form):
    question = forms.CharField(
        label='Ask about your expenses',
        max_length=300,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Example: How much did I spend on food this month?',
                'class': 'query-input',
            }
        ),
    )


class ImportExpensesForm(forms.Form):
    file = forms.FileField(
        label='Upload CSV or XLSX file',
        help_text='Expected columns: category, amount, date, payment_mode',
    )


class SaveQueryForm(forms.Form):
    title = forms.CharField(max_length=120)
    question = forms.CharField(max_length=300)


class BudgetForm(forms.Form):
    category = forms.CharField(max_length=100)
    monthly_limit = forms.IntegerField(min_value=1)
