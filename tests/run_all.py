#!/usr/bin/env python3
"""Unified actual execution: structured legacy suites plus new unittest discovery. No inferred passes."""
import argparse, json, subprocess, sys, unittest, io, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE=Path(__file__).resolve().parent

def legacy(name):
    start=time.monotonic()
    try:
        r=subprocess.run([sys.executable,str(HERE/name),'--json'],capture_output=True,text=True,timeout=180)
        d=json.loads(r.stdout); total=d['total']; passed=d['passed']
        return {'file':name,'ok':r.returncode==0 and total>0 and passed==total,'total':total,'passed':passed,'failed':total-passed,'seconds':round(time.monotonic()-start,3),'results':d['results'],'stderr':r.stderr}
    except Exception as e:return {'file':name,'ok':False,'total':0,'passed':0,'failed':0,'error':str(e)}

def regression():
    start=time.monotonic(); sys.path.insert(0,str(HERE));stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    failed=len(r.failures)+len(r.errors); skipped=len(r.skipped)+len(r.expectedFailures); unexpected=len(r.unexpectedSuccesses)
    return {'file':'test_*.py','ok':r.wasSuccessful() and r.testsRun>0 and not skipped,'total':r.testsRun,'passed':r.testsRun-failed-skipped-unexpected,'failed':failed,'skipped':skipped,'unexpected_successes':unexpected,'seconds':round(time.monotonic()-start,3),'output':stream.getvalue()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');args=p.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(legacy,x) for x in ('run_tests.py','run_scenarios.py')];jobs.append(pool.submit(regression));suites=[j.result() for j in jobs]
    total=sum(s['total'] for s in suites);passed=sum(s['passed'] for s in suites);ok=all(s['ok'] for s in suites)
    out={'total':total,'passed':passed,'failed_or_skipped':total-passed,'all_ok':ok,'suites':suites,'not_executed':['独立真实模型四组对照与人工盲评','真实客户案例及实际宿主','官方原始语料全量复核','真实最终提交文件与签署效力核验']}
    if args.json:print(json.dumps(out,ensure_ascii=False,indent=2))
    else:
        for s in suites:print(f"{s['file']}: {s['passed']}/{s['total']} {'PASS' if s['ok'] else 'FAIL'}")
        print(f'Total: {passed}/{total}; all_ok={ok}');print('NOT EXECUTED: '+', '.join(out['not_executed']))
    return 0 if ok else 1
if __name__=='__main__':sys.exit(main())
