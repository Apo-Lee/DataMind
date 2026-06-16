# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'E:\\Python_Code_Project\\DataMind\\backend')
with open('E:\\Python_Code_Project\\DataMind\\backend\\app\\core\\query_engine.py','r',encoding='utf-8') as f:
    c = f.read()
c = c.replace('\ufeff', '')
try:
    compile(c, 'qe', 'exec')
    print('COMPILE OK')
except SyntaxError as e:
    print(f'ERROR at line {e.lineno}: {e.msg}')
    lines = c.split('\n')
    if e.lineno and e.lineno <= len(lines):
        print(f'  {repr(lines[e.lineno-1][:120])}')
