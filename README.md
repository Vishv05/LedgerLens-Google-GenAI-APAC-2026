# LedgerLens: Google GenAI APAC 2026

LedgerLens is a Django-based smart spend analyzer that leverages Google GenAI for advanced expense analysis and forecasting. This project is designed for easy deployment on cloud platforms and features a user-friendly interface for managing budgets, importing expenses, and generating insights.

## Features
- **Expense Import:** Upload and manage your expenses easily.
- **Budget Management:** Set and track budgets for different categories.
- **Forecasting:** Predict future spending using AI-powered models.
- **Natural Language Query:** Ask questions about your spending in plain English.
- **User Authentication:** Secure login and registration system.
- **Admin Dashboard:** Manage users, budgets, and queries.

## Project Structure
```
LedgerLens-Google-GenAI-APAC-2026/
├── analyzer_app/
│   ├── admin.py
│   ├── apps.py
│   ├── forecasting.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   └── migrations/
├── database/
│   └── sample_data.sql
├── smartspend_project/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── app.js
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── budgets.html
│   └── import_expenses.html
├── db.sqlite3
├── requirements.txt
├── Dockerfile
├── manage.py
└── README.md
```

## Setup & Deployment

### 1. Clone the Repository
```
git clone https://github.com/Vishv05/LedgerLens-Google-GenAI-APAC-2026.git
cd LedgerLens-Google-GenAI-APAC-2026
```

### 2. Install Dependencies
```
pip install -r requirements.txt
```

### 3. Run Migrations
```
python manage.py migrate
```

### 4. Collect Static Files
```
python manage.py collectstatic --noinput
```

### 5. Run the Development Server
```
python manage.py runserver
```

### 6. Docker Deployment (Optional)
Build and run with Docker:
```
docker build -t ledgerlens .
docker run -p 8080:8080 ledgerlens
```

### 7. Cloud Deployment
- **Google Cloud Run:** See the Dockerfile and deployment instructions in this README.
- **Other Platforms:** Compatible with PythonAnywhere, Render.com, and Replit.

## Environment Variables
- Configure your `.env` file for sensitive settings (see `.env.example`).

## License
MIT License

## Author
Vishv05

---

**For more details, see the code and comments in each module.**

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000

## 6. Example Questions

- How much did I spend on food this month?
- Show total spending by category.
- What is my average monthly spending?
- List top 5 highest expenses.

## 7. AlloyDB Integration Later

To use AlloyDB later, set these in `.env`:

- `DB_HOST` = AlloyDB endpoint
- `DB_PORT` = 5432
- `DB_SSLMODE` = require
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` accordingly

No code changes are required because Django already uses PostgreSQL-compatible settings.
