
import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    
    # Remove future import if present (optional cleanup)
    # content = content.replace("from __future__ import annotations\n", "")

    # Replace Type | None with Optional[Type]
    # Handle list["..."] | None etc.
    # We use a pattern that matches balanced brackets roughly or just non-space characters
    # Simple pattern: (\w+(?:\[[^\]]+\])?) \| None
    
    pattern = r'([\w\."\']+(?:\[[^\]]+\])?)\s*\|\s*None'
    
    def replacement(match):
        return f"Optional[{match.group(1)}]"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        # Check if Optional is imported
        if "Optional" in new_content and "from typing import" not in new_content:
             # Add import at the top
             lines = new_content.splitlines()
             # Find insertion point (after docstring or imports)
             insert_idx = 0
             for i, line in enumerate(lines):
                 if line.startswith("import ") or line.startswith("from "):
                     insert_idx = i
                     break
                 if line.strip() == "" and i > 0: # blank line after imports
                     insert_idx = i
                     break
             
             # Just insert at top or after standard imports
             # Simple heuristic: After the last from __future__ or first import
             
             if "from typing import" not in new_content:
                 # Check for existing imports to append or add new line
                 new_content = "from typing import Optional\n" + new_content
        elif "Optional" in new_content and "from typing import" in new_content:
            # Check if Optional is already imported
            if "Optional" not in re.search(r'from typing import ([^\n]+)', new_content).group(1):
                 new_content = re.sub(r'from typing import ([^\n]+)', r'from typing import \1, Optional', new_content)

        print(f"Fixed {filepath}")
        with open(filepath, 'w') as f:
            f.write(new_content)

def main():
    target_dir = "/Users/nikolajunser-richter/minga-greens-erp/backend/tests"
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                fix_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
