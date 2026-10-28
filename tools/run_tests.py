"""Run every tools/test_*.py in parallel (one process each) and print their output in order.

usage: python run_tests.py [name ...]      e.g. python run_tests.py v11 v14
"""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def run(path):
    t = time.time()
    r = subprocess.run([sys.executable, '-I', '-B', path], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=HERE)
    return path, r.returncode, r.stdout + r.stderr, time.time() - t


def main():
    want = sys.argv[1:]
    tests = sorted(f for f in os.listdir(HERE) if f.startswith('test_') and f.endswith('.py')
                   and (not want or any(w in f for w in want)))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(tests)) as ex:
        results = list(ex.map(run, tests))
    failed = 0
    for path, code, out, dt in results:
        status = 'ok' if code == 0 else 'FALHOU (%d)' % code
        failed += code != 0
        print('=== %s  %s  %.0fs' % (path, status, dt))
        print(out.rstrip())
    print('\n%d testes, %d falharam, %.0fs no total' % (len(results), failed, time.time() - t0))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
