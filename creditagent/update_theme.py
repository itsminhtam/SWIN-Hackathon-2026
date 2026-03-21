import sys

with open('ui/app.py', 'r', encoding='utf-8') as f:
    code = f.read()

reps = {
    '.main { background-color: #0a0e1a; }': '.main { background-color: #f8fafc; }',
    '.stApp { background: linear-gradient(135deg, #0a0e1a 0%, #0f172a 50%, #0a0e1a 100%); }': '.stApp { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #f8fafc 100%); }',
    'background: linear-gradient(135deg, #1e293b, #0f172a);': 'background: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);',
    'background: linear-gradient(135deg, #60a5fa, #a78bfa);': 'background: linear-gradient(135deg, #2563eb, #7c3aed);',
    'border: 1px solid #334155;': 'border: 1px solid #e2e8f0;',
    'background: #1e293b;': 'background: #ffffff;',
    'border-bottom: 1px solid #1e293b;': 'border-bottom: 1px solid #e2e8f0;',
    'color:#e2e8f0': 'color:#1e293b',
    'color:#94a3b8': 'color:#64748b',
    'color:#60a5fa': 'color:#3b82f6',
    'color:#a78bfa': 'color:#8b5cf6',
    'paper_bgcolor="#0f172a"': 'paper_bgcolor="rgba(0,0,0,0)"',
    'plot_bgcolor="#0f172a"': 'plot_bgcolor="rgba(0,0,0,0)"',
    '"color": "#e2e8f0"': '"color": "#1e293b"',
    '"color": "#94a3b8"': '"color": "#64748b"',
    '"color": "#1f1315"': '"color": "#fef2f2"',
    '"color": "#1c1207"': '"color": "#fffbeb"',
    '"color": "#1c1a07"': '"color": "#fefce8"',
    '"color": "#071c11"': '"color": "#ecfdf5"',
    'gridcolor": "#1e293b"': 'gridcolor": "#e2e8f0"',
    '"tickcolor": "#475569"': '"tickcolor": "#cbd5e1"'
}

for k, v in reps.items():
    code = code.replace(k, v)

with open('ui/app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Theme updated successfully")
