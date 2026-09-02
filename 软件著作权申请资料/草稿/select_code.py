import json, os

p = r'D:/Workplace/AISci/软件著作权申请资料/草稿/代码文件选择.json'
d = json.load(open(p, encoding='utf-8'))
files = d['files']

EXCLUDE = ['venv/', 'node_modules/', 'shaxiang-main/', 'pingfenbiao-main/',
           'report-scorer-suite/', 'output/', 'designs/', 'docs/', '_cmp/',
           '_ppt_assets/', 'storage/', 'logs/', '.pytest_cache', '__pycache__',
           'migrations/', '.github', 'data/']

def is_biz(path):
    low = path.lower()
    if any(seg in low for seg in EXCLUDE):
        return False
    if path.startswith('frontend/src/'):
        if low.endswith(('.ts', '.tsx', '.js', '.jsx')) and 'test' not in low and '__tests__' not in low:
            return True
    if path.startswith('backend/app/'):
        if low.endswith('.py') and '__pycache__' not in low and 'test' not in low and 'migrations' not in low:
            return True
    return False

CORE_COMPONENTS = ['workflowpage', 'literaturelibrary', 'hypothesespage', 'loopconfigpanel',
                   'evidencechaindrawer', 'pipelineprogress', 'closedlooptimeline', 'hitlgatemodal',
                   'hypothesiscard', 'evidencelevelbadge', 'promptmanagementpage', 'coordinatorhints', 'navbar']

def sort_key(path):
    low = path.lower()
    if path.startswith('frontend/src/'):
        if 'main.tsx' in low or 'app.tsx' in low:
            return (0, 0)
        if 'router' in low:
            return (0, 1)
        base = os.path.basename(low).replace('.tsx', '').replace('.ts', '').replace('.jsx', '').replace('.js', '')
        if base in ('workflowpage', 'literaturelibrary'):
            return (0, 5.5)
        if any(c in base for c in CORE_COMPONENTS):
            return (0, 3)
        if '/services/' in low:
            return (0, 5)
        if '/pages/' in low or low.endswith('page.tsx'):
            return (0, 6)
        if '/components/' in low:
            return (0, 4)
        if '/store/' in low or 'store' in low:
            return (0, 7)
        if '/utils/' in low or 'utils' in low:
            return (0, 8)
        return (0, 9)
    else:  # backend/app
        if '/prompts/' in low:
            return (1, 10)
        if '/skills/' in low:
            return (1, 11)
        if low.endswith('main.py') or low.endswith('__init__.py'):
            return (1, 12)
        if '/agents/' in low:
            return (1, 13)
        if '/api/' in low:
            return (1, 14)
        if '/core/' in low:
            return (1, 15)
        return (1, 16)

selected, others = [], []
for f in files:
    if is_biz(f['path']):
        selected.append(f)
    else:
        f['selected'] = False
        if 'model_reason' not in f:
            f['model_reason'] = ''
        others.append(f)

selected.sort(key=lambda f: sort_key(f['path']))
for f in selected:
    f['selected'] = True
    tier = '前端' if f['path'].startswith('frontend/') else '后端'
    f['model_reason'] = f'【{tier}业务源码】{f["path"]}，体现软件真实功能与运行逻辑，选入软著代码材料。'

d['files'] = selected + others
total_lines = sum(f.get('material_line_count', f.get('line_count', 0)) for f in selected)
print('selected files:', len(selected))
print('selected material lines (approx):', total_lines)
print('estimated pages (50/页):', total_lines // 50 + (1 if total_lines % 50 else 0))
print('--- first 12 selected ---')
for f in selected[:12]:
    print('  ', f['path'], f.get('material_line_count', '?'))
print('--- last 8 selected ---')
for f in selected[-8:]:
    print('  ', f['path'], f.get('material_line_count', '?'))

json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('written back:', p)
