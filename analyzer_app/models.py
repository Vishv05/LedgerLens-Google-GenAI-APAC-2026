from django.db import models
from django.contrib.auth.models import User


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses', null=True, blank=True)
    category = models.CharField(max_length=100)
    amount = models.IntegerField()
    date = models.DateField()
    payment_mode = models.CharField(max_length=100)

    class Meta:
        db_table = 'expenses'
        ordering = ['-date', 'id']

    def __str__(self):
        return f"{self.category} - {self.amount} on {self.date}"


class SavedQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_queries')
    title = models.CharField(max_length=120)
    question = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class QueryHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='query_history')
    question = models.CharField(max_length=300)
    generated_sql = models.TextField(blank=True)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.question[:40]}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.CharField(max_length=100)
    monthly_limit = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'category')
        ordering = ['category']

    def __str__(self):
        return f"{self.user.username} - {self.category}: {self.monthly_limit}"
