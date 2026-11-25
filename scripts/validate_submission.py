#!/usr/bin/env python3
"""Controlled preflight; never issues official submission approval or trusts case review flags."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
import kb, validate_eligibility as VE, integrity as I

READY='HUMAN_REVIEW_REQUIRED'
TECHNICAL_READY='READY_FOR_HUMAN_REVIEW'

def strict_json(path):
    def pairs(p):
        d={}
        for k,v in p:
            if k in d: raise ValueError('重复 JSON 键: '+k)
            d[k]=v
        return d
    def bad(s): raise ValueError('非法数值: '+s)
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=bad)

def run_auditor(script,doc):
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'input.json'; p.write_text(json.dumps(doc,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        r=subprocess.run([sys.executable,str(Path(__file__).with_name(script)), '--file',str(p),'--json'],capture_output=True,text=True,timeout=30)
        out=json.loads(r.stdout); counts=out['counts']
        if r.returncode!=0 or counts.get('P0') or counts.get('P1'):
            return [f'{script}: '+json.dumps(out.get('findings',[]),ensure_ascii=False)[:1200]]
        return []

def technical_preflight(case,award,root):
    gates=[]; manifest={}; claims={}; matched={}
    def gate(gid,title,fn):
        try: errors=fn(); errors=list(errors or [])
        except Exception as e: errors=[f'校验未完成: {type(e).__name__}: {e}']
        gates.append({'gate':gid,'title':title,'passed':not errors,'check_status':'PASS' if not errors else 'FAIL_OR_UNKNOWN','detail':'本地契约检查通过（非语义/来源认证）' if not errors else '；'.join(errors)[:2500]})
    def rules():
        errors=[]
        if type(case.get('competition_year')) is not int or case['competition_year']!=2026: errors.append('必须显式锁定2026规则；其他年度未知')
        if case.get('award_id')!=award: errors.append('案例奖项与命令不一致')
        a=kb.rules_for(award)
        if not a or any(x.get('verification_status')!='VERIFIED' and x.get('enforcement_level')=='official_mandatory' for x in a): errors.append('存在未核实强制规则或规则缺失')
        for k in ('eligibility_window','eligibility_region','max_categories_per_activity','video_max_seconds','video_max_mb','print_min_count','print_max_count','print_max_mb'):
            if kb.rule_value(award,k) is None: errors.append('规则缺失/未核实: '+k)
        return errors
    gate('G01','年度规则快照完整性（非官方原文复核）',rules)
    def elig():
        errors=[]; nums=case.get('category_numbers')
        if not isinstance(nums,list) or not nums or any(type(n) is not int for n in nums) or len(nums)!=len(set(nums)): return ['类别编号缺失、重复或类型不合法']
        for k in ('has_pilot_only','has_other_activities_in_period'):
            if k=='has_pilot_only' and type(case.get(k)) is not bool: errors.append('缺显式非试点确认')
        a=VE.parse_date(case.get('implementation_start')); b=VE.parse_date(case.get('implementation_end'))
        if not a or not b or a>b: errors.append('实施日期缺失或倒序')
        for fn in (VE.check_year_covered,VE.check_window,VE.check_region,VE.check_categories,VE.check_test_project,VE.check_agency_anonymity,VE.check_data_source):
            c=fn(case,award)
            if c.status!='PASS': errors.append(f'{c.cid}:{c.status}:{c.detail}')
        return errors
    gate('G02','参赛资格结构检查',elig)
    def categories():
        errors=[]
        for n in case.get('category_numbers') or []:
            c=kb.get_category(n,award)
            if not c or not I.meaningful(c.get('definition_zh')): errors.append(f'未知类别或定义缺失: {n}')
        c=VE.check_category_special(case,award)
        if c.status!='PASS': errors.append(c.detail)
        return errors
    gate('G03','类别约束',categories)
    def evidence():
        nonlocal matched,claims
        errors,matched,claims=I.evidence_audit(case,root)
        for e in matched.values(): manifest[e['record']['file']]=e['sha256']
        return errors
    gate('G05','原始文件、引用与主张本地匹配',evidence)
    gate('G04','必填字段、字数及正文反向绑定',lambda:I.field_audit(case,award,claims))
    def metrics():
        errors=I.metric_audit(case,claims,matched)
        if not errors: errors+=run_auditor('validate_metrics.py',{'goals':case['goals'],'metrics':case['metrics'],'narrative_flags':case.get('narrative_flags') or {}})
        return errors
    gate('G06','指标与计算审查',metrics)
    def versions():
        vs=case.get('versions') or []
        if not isinstance(vs,list): return ['versions 必须为列表']
        # A preflight covers one immutable case only, not multiple independent drafts.
        if vs: return ['请逐份预检各类别版本，并由人工执行跨版本事实对照；本入口不接受未绑定版本']
        return []
    gate('G07','单份材料范围锁定',versions)
    def materials():
        errors,files=I.artifact_audit(case,award,root); manifest.update(files)
        if case.get('external_links_in_form') or case.get('agencies_in_materials'): errors.append('存在外链或代理商标识')
        for v in [case.get('creative_video') or {},*(case.get('creative_print') or [])]:
            if v.get('has_agency_name') is not False: errors.append('素材匿名性未声明或存在冲突；还需人工观看')
        return errors
    gate('G08','实际素材文件预检',materials)
    def auth():
        a=case.get('authorization') or {}; errors=[]
        if a.get('client_authorized') is not True or a.get('agreement_signed') is not True or a.get('publication_option') not in {'as_submitted','edited'}: errors.append('缺授权声明/发布选项')
        if a.get('publication_option')=='edited': errors.append('编辑公开版尚无独立正文绑定验证；须人工处理')
        for eid,e in matched.items():
            r=e['record']
            if r.get('confidentiality') in {'high','secret'} or r.get('publication_cleared') is not True: errors.append(f'{eid}: 未获公开许可或高保密，禁止进入公开材料预检')
        return errors
    gate('G09','授权文件登记及公开权限冲突预检',auth)
    def attribution():
        a=case.get('attribution') or {}; errors=[]
        if a.get('claimed_conclusion') not in {'A','B','C','D','E'}: errors.append('缺明确归因结论等级')
        if type(a.get('has_parallel_campaigns')) is not bool: errors.append('缺同期活动声明')
        if a.get('section_4_2_text')!= (case.get('answers') or {}).get('P4_04'): errors.append('归因正文与正式字段不一致')
        ids=a.get('evidence_ids') or []
        if not ids or any(i not in matched for i in ids): errors.append('归因未绑定原始证据')
        if a.get('claimed_conclusion') in {'A','B'}: errors.append('强因果/贡献结论需要独立方法与原始数据人工复核，本地预检暂不放行；不得无据降级包装')
        errors+=run_auditor('audit_attribution.py',a)
        return errors
    gate('G11','归因审计（调用实际脚本）',attribution)
    gate('G10','重大问题及前置门禁',lambda:[g['gate']+' 未通过' for g in gates if not g['passed']]+['存在登记未决问题' for k in ('open_p0_issues','open_p1_issues') if case.get(k)])
    gates.sort(key=lambda g:g['gate']); failed=[g['gate'] for g in gates if not g['passed']]
    status=TECHNICAL_READY if not failed else ('BLOCKED' if set(failed)&{'G01','G02','G03','G04','G08','G09','G11'} else 'NEEDS_EVIDENCE' if set(failed)&{'G05','G06'} else 'BLOCKED')
    # No trusted human identity/signature infrastructure exists. No READY_TO_SUBMIT issuer.
    snapshot=hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
    return {'award_id':award,'status':status,'gates':gates,'failed_gates':failed,'case_sha256':snapshot,'file_manifest':manifest,'human_review_required':True,'official_source_reverified':False,'submission_authorized':False,'human_review_tasks':['官方原文与现行年度规则','证据来源真实性、语义与组合主张','类别适配及专业营销判断','归因方法、操作数语义与实际数据','最终正文和素材匿名、格式及外链','真实授权签署人与公开版权限','跨类别事实一致性（如适用）']}

def preflight(case,award,root):
    from human_review import assess
    return assess(case,root,technical_preflight(case,award,root))

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--case',required=True); ap.add_argument('--award',required=True); ap.add_argument('--base-dir'); ap.add_argument('--json',action='store_true'); args=ap.parse_args()
    try:
        c=strict_json(args.case)
        if not isinstance(c,dict) or not kb.get_award(args.award): raise ValueError('未知奖项或案例不是对象')
        out=preflight(c,args.award,args.base_dir)
    except Exception as e:
        out={'status':'BLOCKED','error':f'{type(e).__name__}: {e}','gates':[],'failed_gates':['INPUT'],'submission_authorized':False}
    if args.json: print(json.dumps(out,ensure_ascii=False,indent=2))
    else:
        for g in out['gates']: print(f"[{'PASS' if g['passed'] else 'FAIL'}] {g['gate']} {g['title']}: {g['detail']}")
        print('交付状态: '+out['status']); print(out.get('error','仅为本地预检，不授权提交。'))
    return 1  # no final authorization or complete review in this entrypoint
if __name__=='__main__': sys.exit(main())
