
import os
import re

files_to_fix = [
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/production.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/capacity.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/product.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/seed.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/invoice.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/unit.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/customer.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/inventory.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/order.py",
    "/Users/nikolajunser-richter/minga-greens-erp/backend/app/models/forecast.py"
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}")
        return
        
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Update imports
    # Remove dialect import if clean, or replace types
    # Case: from sqlalchemy.dialects.postgresql import UUID, JSONB
    if "from sqlalchemy.dialects.postgresql import" in content:
        # Check if generic imports exist
        if "from sqlalchemy import" in content:
            # Append Uuid, JSON to existing import if possible, but cleaner to just add separate import
             pass
        
        # Replace the dialect import with mapping to generic types
        # We want: from sqlalchemy import Uuid, JSON (or ensure they are available)
        # And remove the dialect line.
        
        # Strategy: Replace "from sqlalchemy.dialects.postgresql import X, Y" with NO_OP (empty) 
        # and ensure "from sqlalchemy import ..., Uuid, JSON" is present?
        # Or simpler: Change the import line to import aliases?
        # "from sqlalchemy.types import Uuid as UUID, JSON as JSONB" <- This keeps usage valid?
        # But UUID(as_uuid=True) constructor call fails with Uuid type class.
        
        # Better: Replace usage.
        
        content = re.sub(r'from sqlalchemy\.dialects\.postgresql import [^(\n]+', '', content)
        # Clean up empty lines or double newlines?
        
        # Add imports at top (after typical sqlalchemy imports)
        # Find "from sqlalchemy.orm import" or similar and insert "from sqlalchemy.types import Uuid, JSON"
        if "from sqlalchemy.orm import" in content:
            content = content.replace("from sqlalchemy.orm import", "from sqlalchemy.types import Uuid, JSON\nfrom sqlalchemy.orm import")
        elif "from sqlalchemy import" in content:
             content = content.replace("from sqlalchemy import", "from sqlalchemy.types import Uuid, JSON\nfrom sqlalchemy import")
        
    
    # 2. Replace type usages
    # UUID(as_uuid=True) -> Uuid
    content = content.replace("UUID(as_uuid=True)", "Uuid")
    
    # JSONB -> JSON
    content = content.replace("JSONB", "JSON")
    
    # ARRAY -> JSON
    # Replace ARRAY(Integer) or similar with JSON
    # Regex for ARRAY(...) -> JSON
    content = re.sub(r'ARRAY\([^)]+\)', 'JSON', content)
    content = content.replace("ARRAY", "JSON") # Fallback if just ARRAY imported/used
    
    # Remaining UUID usages (as type annotation or mapped_column arg without parens)
    # Check for mapped_column(UUID, ...) -> mapped_column(Uuid, ...)
    # But wait, python uuid.UUID exists too.
    # Usages:
    # id: Mapped[uuid.UUID] -> Keep (python type)
    # mapped_column(UUID(as_uuid=True)...) -> Became mapped_column(Uuid...)
    # mapped_column(UUID...) -> Replace UUID with Uuid if it's the SQL type.
    
    # Problem: How to distinguish SQL UUID from python uuid.UUID if imported as UUID?
    # Use explicit names.
    # In files, typically: import uuid.
    # And SQL UUID was imported from dialects.
    
    # If I removed the import of UUID from dialects, then any usage of UUID (SQL type) will be defined by my new import `Uuid`.
    # But I imported `Uuid`. I did NOT alias it as `UUID`.
    # So I must replace `UUID` with `Uuid` in usages.
    # BUT `uuid.UUID` (python) is used in Mapped[].
    # `uuid.UUID` is safe because it uses module prefix.
    
    # What about un-prefixed `UUID`?
    # If code says `mapped_column(UUID, ...)` -> transform to `mapped_column(Uuid, ...)`
    
    # Regex to replace UUID that is NOT `uuid.UUID` and NOT inside string.
    # Simple replace "UUID" -> "Uuid".
    # BUT `uuid.UUID` -> `uuid.Uuid` (WRONG).
    # So look for `UUID` starting with non-dot?
    # Or just replace `mapped_column(UUID` -> `mapped_column(Uuid`.
    
    content = content.replace("mapped_column(UUID", "mapped_column(Uuid")
    content = content.replace("SQLEnum(UUID", "SQLEnum(Uuid") # Unlikely
    
    # Clean up imports
    # Remove multiple imports of Uuid, JSON if I added duplicates
    
    if content != original_content:
        print(f"Fixing {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)

if __name__ == "__main__":
    for f in files_to_fix:
        fix_file(f)
