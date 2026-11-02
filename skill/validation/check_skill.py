# -*- coding: utf-8 -*-
"""check_skill.py -- 技能包自检（不依赖本工程项目，仅需 Python 3.8+）

用法：
    python skill/validation/check_skill.py
退出码：0 = 全部通过；1 = 有失败项

检查项：
  1. 必备文件/目录存在
  2. skill.json 合法且入口文件存在
  3. Markdown 相对链接可解析（不含 http/anchor）
  4. 全部 .py 可编译
  5. 文件/目录命名为纯英文小写（README.md 例外）
  6. 各技能条目数量达标（提示词>=8、案例模板>=6、踩坑>=18）
  7. evidence.md 中反引号引用的包内路径真实存在
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PKG = os.path.dirname(SKILL)

fail = 0
warn = 0
passn = 0


def ok(msg):
    global passn
    passn += 1
    print('[PASS] ' + msg)


def bad(msg):
    global fail
    fail += 1
    print('[FAIL] ' + msg)


def wn(msg):
    global warn
    warn += 1
    print('[WARN] ' + msg)


REQUIRED_FILES = [
    'README.md',
    'skill.json',
    'workflow.md',
    'prompt_workflows.md',
    'case_templates.md',
    'pitfalls.md',
    'evidence.md',
    'changelog.md',
    'validation/README.md',
    'validation/check_package.py',
    'pynq/README.md',
]
REQUIRED_DIRS = ['validation', 'pynq']

# ---------- 1) 必备文件 ----------
for rel in REQUIRED_FILES:
    p = os.path.join(SKILL, rel.replace('/', os.sep))
    if os.path.isfile(p):
        ok('file exists: ' + rel)
    else:
        bad('missing file: ' + rel)
for rel in REQUIRED_DIRS:
    p = os.path.join(SKILL, rel)
    ok('dir exists: ' + rel) if os.path.isdir(p) else bad('missing dir: ' + rel)

# ---------- 2) skill.json ----------
jp = os.path.join(SKILL, 'skill.json')
if os.path.isfile(jp):
    try:
        data = json.load(io.open(jp, encoding='utf-8'))
        for key in ('name', 'version', 'description', 'entrypoints', 'skills'):
            if key in data:
                ok('skill.json has key: ' + key)
            else:
                bad('skill.json missing key: ' + key)
        eps = data.get('entrypoints', {})
        for name, rel in eps.items():
            p = os.path.join(SKILL, rel.replace('/', os.sep))
            ok('entrypoint exists: %s -> %s' % (name, rel)) if os.path.isfile(p) else bad('entrypoint missing: %s -> %s' % (name, rel))
    except Exception as e:
        bad('skill.json invalid: %s' % e)

# ---------- 3) markdown 相对链接 ----------
LINK = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
for root, dirs, files in os.walk(SKILL):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
    for f in files:
        if not f.endswith('.md'):
            continue
        p = os.path.join(root, f)
        t = io.open(p, encoding='utf-8', errors='ignore').read()
        for m in LINK.finditer(t):
            href = m.group(1).strip()
            if href.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            href = href.split('#', 1)[0].strip()
            if not href:
                continue
            target = os.path.normpath(os.path.join(root, href.replace('/', os.sep)))
            if os.path.exists(target):
                pass
            else:
                bad('broken link in %s: %s' % (os.path.relpath(p, SKILL), href))
ok('markdown links checked')

# ---------- 4) python 编译 ----------
import py_compile
pyfiles = []
for root, dirs, files in os.walk(SKILL):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            pyfiles.append(os.path.join(root, f))
for p in pyfiles:
    try:
        py_compile.compile(p, doraise=True)
        ok('py compile: ' + os.path.relpath(p, SKILL))
    except Exception as e:
        bad('py compile failed: %s (%s)' % (os.path.relpath(p, SKILL), e))

# ---------- 5) 命名 ----------
BADNAME = re.compile(r'[^a-z0-9_.-]')
for root, dirs, files in os.walk(SKILL):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
    for name in list(dirs) + files:
        if name == 'README.md':
            continue
        if BADNAME.search(name):
            bad('non-lowercase-ascii name: ' + os.path.relpath(os.path.join(root, name), SKILL))
ok('naming checked')

# ---------- 6) 条目数量 ----------
def count_headers(rel, pattern):
    p = os.path.join(SKILL, rel)
    if not os.path.isfile(p):
        return 0
    t = io.open(p, encoding='utf-8', errors='ignore').read()
    return len(re.findall(pattern, t, flags=re.M))


n_prompt = count_headers('prompt_workflows.md', r'^##\s+\d+\.')
n_case = count_headers('case_templates.md', r'^##\s+模板\s+[A-Z]')
n_pit = count_headers('pitfalls.md', r'^##\s+P\d+\.')
ok('prompts: %d (>=8)' % n_prompt) if n_prompt >= 8 else bad('prompts %d < 8' % n_prompt)
ok('case templates: %d (>=6)' % n_case) if n_case >= 6 else bad('case templates %d < 6' % n_case)
ok('pitfalls: %d (>=18)' % n_pit) if n_pit >= 18 else bad('pitfalls %d < 18' % n_pit)

# ---------- 7) evidence 内路径存在 ----------
ep = os.path.join(SKILL, 'evidence.md')
if os.path.isfile(ep):
    t = io.open(ep, encoding='utf-8', errors='ignore').read()
    refs = set(re.findall(r'(?:^|[\s`(（])([^\s`()（）]+\.(?:md|txt|rpt|csv|py|png|json))', t))
    for r in sorted(refs):
        if r.startswith(('http', '/')):
            continue
        cand = os.path.normpath(os.path.join(PKG, r.replace('/', os.sep)))
        if os.path.exists(cand):
            ok('evidence path exists: ' + r)
        else:
            # 允许相对 skill/ 路径
            cand2 = os.path.normpath(os.path.join(SKILL, r.replace('/', os.sep)))
            if os.path.exists(cand2):
                ok('evidence path exists: ' + r)
            else:
                wn('evidence path not found in package: ' + r)

print('')
print('===== SUMMARY: %d passed, %d failed, %d warnings =====' % (passn, fail, warn))
if fail == 0:
    print('ALL CHECKS PASSED')
    sys.exit(0)
print('CHECKS FAILED')
sys.exit(1)
