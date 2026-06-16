import sys
sys.path.insert(0, 'E:\\Python_Code_Project\\DataMind\\backend')
p = 'E:\\Python_Code_Project\\DataMind\\backend\\app\\core\\query_engine.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('\\ufeff', '')
try:
    compile(content, 'query_engine.py', 'exec')
    print('COMPILE OK')
except SyntaxError as e:
    print(f'ERROR line {e.lineno}: {e.msg}')
    lines = content.split('\\n')
    if e.lineno and e.lineno <= len(lines):
        print(f'  {repr(lines[e.lineno-1][:150])}')