
import os

files_to_fix = [
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/invoice.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/inventory.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/production.py"
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} (not found)")
        return
        
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace table name in foreign keys
    new_content = content.replace('"order_items.id"', '"order_lines.id"')
    new_content = new_content.replace("'order_items.id'", "'order_lines.id'")
    
    if new_content != content:
        print(f"Fixing {filepath}")
        with open(filepath, 'w') as f:
            f.write(new_content)

if __name__ == "__main__":
    for f in files_to_fix:
        fix_file(f)
