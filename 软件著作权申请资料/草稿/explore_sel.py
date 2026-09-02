import json
p = r'D:/Workplace/AISci/软件著作权申请资料/草稿/代码文件选择.json'
d = json.load(open(p, encoding='utf-8'))
print('type', type(d).__name__)
if isinstance(d, dict):
    print('keys', list(d.keys()))
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print('FILES in', k, 'len', len(v))
            print('item keys', list(v[0].keys()))
            print('sample', v[0])
            break
elif isinstance(d, list):
    print('list len', len(d))
    print('item0 keys', list(d[0].keys()))
    print('sample', d[0])
