"""Run every automated test (v0.19.0).

How to use (in the VS Code terminal, inside the project folder, with the venv active):
    python tests/run_tests.py                 check the AGENTS.md rules, then run every test file
    python tests/run_tests.py test_sales      run only the files whose name contains "test_sales"
    python tests/run_tests.py -v              also print every PASS line, not only failures

Why it is safe to run on your own computer:
each test file runs in a fresh TEMPORARY COPY of the project. The tests delete and rebuild the
database many times, but only in that copy. Your real instance/ folder (database + secret key),
uploaded pictures and local_demo/ are never copied, read or changed. The copy is deleted at the end.

Only Python's standard library is used, so nothing extra has to be installed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
# Never copied into the test folder: private data, uploads, Git history and large documentation files.
SKIP = {'.git', 'instance', 'venv', '.venv', '__pycache__', 'local_demo', 'screenshots', 'diagrams', 'guides'}
SKIP_UPLOADS = {os.path.join('static', 'avatars'), os.path.join('static', 'products')}
TIME_LIMIT = 300   # seconds per test file


def ignore(folder, names):
    """Tell shutil.copytree which files and folders to leave out of the copy."""
    relative = os.path.relpath(folder, PROJECT)
    left_out = set()
    for name in names:
        path = os.path.normpath(os.path.join(relative, name))
        if name in SKIP or path in SKIP_UPLOADS or name.endswith('.db'):
            left_out.add(name)
    return left_out


def run_one(test_file, verbose):
    """Copy the project to a temporary folder, run one test file there, return (passed, output, seconds)."""
    work = tempfile.mkdtemp(prefix='pos_test_')
    try:
        copy = os.path.join(work, 'project')
        shutil.copytree(PROJECT, copy, ignore=ignore)
        environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', POS_TEST_COPY='1')
        environment.pop('SECRET_KEY', None)     # tests make their own key in the copy
        environment.pop('FLASK_DEBUG', None)
        start = time.time()
        try:
            result = subprocess.run([sys.executable, os.path.join('tests', test_file)], cwd=copy, env=environment,
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=TIME_LIMIT)
            output, passed = result.stdout + result.stderr, result.returncode == 0
        except subprocess.TimeoutExpired:
            output, passed = f'  FAIL  took longer than {TIME_LIMIT} seconds', False
        return passed, output, time.time() - start
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    sys.stdout.reconfigure(errors='replace')   # a Windows window that can't show "₱" shows "?" instead of crashing
    verbose = '-v' in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith('-')]
    tests = sorted(f for f in os.listdir(HERE) if f.startswith('test_') and f.endswith('.py'))
    if wanted:
        tests = [t for t in tests if any(w in t for w in wanted)]
    if not tests:
        print('No test files matched.'); return 1
    failed = []
    if not wanted:   # the full run starts with the AGENTS.md rules (read-only, on the real folder)
        contract = subprocess.run([sys.executable, os.path.join(HERE, 'check_contract.py')], capture_output=True,
                                  text=True, encoding='utf-8', errors='replace')
        lines = contract.stdout.rstrip().splitlines()
        print(f"{'PASS' if contract.returncode == 0 else 'FAIL'}  {'check_contract.py':28}        {lines[-1] if lines else contract.stderr}")
        if contract.returncode != 0:
            failed.append('check_contract.py')
            for line in lines:
                if verbose or line.startswith(('  FAIL', '      ')):
                    print('    ' + line.strip())
        tests_total = len(tests) + 1
    else:
        tests_total = len(tests)
    for test_file in tests:
        passed, output, seconds = run_one(test_file, verbose)
        lines = output.rstrip().splitlines()
        summary = lines[-1] if lines else '(no output)'
        print(f"{'PASS' if passed else 'FAIL'}  {test_file:28} {seconds:5.1f}s  {summary}")
        if verbose or not passed:   # on a failure show everything except the PASS lines
            for line in lines[:-1]:
                if verbose or not line.startswith('  PASS'):
                    print('    ' + line.strip())
        if not passed:
            failed.append(test_file)
    print()
    if failed:
        print(f'{len(failed)} of {tests_total} FAILED: ' + ', '.join(failed))
        return 1
    print(f'All {tests_total} passed (contract check + test files).' if not wanted else f'All {tests_total} test files passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
