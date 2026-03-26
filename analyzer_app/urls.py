from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.legacy_login_redirect, name='legacy_login_redirect'),
    path('logout/', views.legacy_login_redirect, name='legacy_logout_redirect'),
    path('register/', views.legacy_login_redirect, name='legacy_register_redirect'),
    path('', views.index, name='index'),
    path('import-expenses/', views.import_expenses, name='import_expenses'),
    path('save-query/', views.save_query, name='save_query'),
    path('saved-query/<int:saved_query_id>/delete/', views.delete_saved_query, name='delete_saved_query'),
    path('budgets/', views.manage_budgets, name='manage_budgets'),
    path('download-results-csv/', views.download_results_csv, name='download_results_csv'),
]
