import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.celery_app import celery_app
# Explicitly import the modules to ensure tasks are registered
import app.tasks.forecast_tasks
import app.tasks.subscription_tasks

print("Celery app loaded successfully")
print(f"Registered tasks: {list(celery_app.tasks.keys())}")
