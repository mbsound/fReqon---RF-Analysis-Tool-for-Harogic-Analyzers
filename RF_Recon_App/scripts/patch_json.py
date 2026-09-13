import sys

with open('gui.py', 'r') as f:
    content = f.read()

if 'import json' not in content:
    content = content.replace('import sys\n', 'import sys\nimport json\n')
    with open('gui.py', 'w') as f:
        f.write(content)
