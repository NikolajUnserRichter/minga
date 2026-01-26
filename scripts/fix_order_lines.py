
import os

files_to_fix = [
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/tasks/report_tasks.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/tasks/forecast_tasks.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/schemas/__init__.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/api/v1/forecasting.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/services/invoice_service.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/services/inventory_service.py"
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} (not found)")
        return
        
    with open(filepath, 'r') as f:
        content = f.read()
    
    new_content = content.replace("OrderItem", "OrderLine")
    
    if new_content != content:
        print(f"Fixing {filepath}")
        with open(filepath, 'w') as f:
            f.write(new_content)

if __name__ == "__main__":
    for f in files_to_fix:
        fix_file(f)
