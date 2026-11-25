import sys,json,copy,time
from pathlib import Path
# Usage: python rc_attacks.py /path/to/extracted/effie-entry-expert
sys.path.insert(0,str(Path(sys.argv[1]).resolve()/'tests'))
from test_integrity_v11 import Integrity,I,S
f=Integrity(); f.setUp(); base=f.positive_case(); root=f.root
results=[]
def run(name,mut,expected):
 c=copy.deepcopy(base); mut(c); o=S.preflight(c,'EFFIE_GC_MAIN',root); results.append({'name':name,'expected':expected,'status':o['status'],'failed_gates':o['failed_gates'],'submission_authorized':o['submission_authorized'],'details':{g['gate']:g['detail'] for g in o['gates'] if not g['passed']}}); print(name,o['status'],o['failed_gates'],flush=True)
def rewrite(c,changes):
 e=c['evidence'][0]; r=json.loads(e['quote']);r.update(changes);p=root/('new'+str(len(results))+'.txt');p.write_text(json.dumps(r,ensure_ascii=False));e.update(file=p.name,sha256=I.digest(p),quote=p.read_text()); cl=c['claims'][0]; cl['text']=I.render_fact(r)
 for k in ['period','scope','metric','provider']: e[k]=r[k]
 for k in ['period','scope','metric','unit','value']: cl[k]=r[k]
 for k in ['period','scope','unit','value','denominator','baseline','baseline_period']: c['metrics'][0][k]=r[k]
 c['metrics'][0].update(name=r['metric'],source=r['provider']);c['goals'][0]['kpi']=r['metric']
 for k,v in c['answer_bindings'].items():
  if v==['C1']:c['answers'][k]=cl['text']
 c['attribution']['section_4_2_text']=c['answers']['P4_04']
run('baseline_repeated_fact_every_field',lambda c:None,'manual review only; content completeness not established')
run('arbitrary_provider_forged_record',lambda c:rewrite(c,{'provider':'某独立审计机构','value':'90000000'}),'provenance unknown')
run('metric_label_contains_unverified_claim',lambda c:rewrite(c,{'metric':'销量（营销使利润翻倍）'}),'block semantic injection')
run('out_of_campaign_period',lambda c:rewrite(c,{'period':'2035','baseline_period':'2034'}),'flag time mismatch')
def contradiction(c):
 e=copy.deepcopy(c['evidence'][0]);r=json.loads(e['quote']);r['value']='1';p=root/'contradict.txt';p.write_text(json.dumps(r,ensure_ascii=False));e.update(evidence_id='Econflict',file=p.name,quote=p.read_text(),sha256=I.digest(p));c['evidence'].append(e);cl=copy.deepcopy(c['claims'][0]);cl.update(claim_id='Cconflict',text=I.render_fact(r),value='1',evidence_ids=['Econflict']);c['claims'].append(cl);c['answers']['P4_04']+=' '+cl['text'];c['answer_bindings']['P4_04'].append('Cconflict');c['attribution']['section_4_2_text']=c['answers']['P4_04']
run('contradictory_sources_same_scope_period',contradiction,'block unresolved contradiction')
run('goal_without_target',lambda c:c['goals'][0].update(target=''), 'flag missing objective target')
run('same_authorization_file_twice',lambda c:c['authorization'].update(signed_agreement_file=c['authorization']['client_authorization_file']),'manual review only')
def context(c):
 e=c['evidence'][0];p=root/'context.txt';p.write_text(e['quote']+'\n以上为虚构目标，并非实际结果。');e.update(file=p.name,sha256=I.digest(p))
run('record_followed_by_disclaimer',context,'block selective quote')
def natural(c):
 e=c['evidence'][0];p=root/'natural.txt';p.write_text('示例品牌2025年全渠道销售额100元，2024年为90元。');e.update(file=p.name,sha256=I.digest(p),quote=p.read_text()); c['claims'][0]['text']=e['quote'];
 for k,v in c['answer_bindings'].items():
  if v==['C1']:c['answers'][k]=e['quote']
 c['attribution']['section_4_2_text']=c['answers']['P4_04']
run('legitimate_natural_language_metric',natural,'manual extraction route; no automatic certification')
run('metric_omitted_from_all_answers',lambda c: [c['answers'].update({k:c['claims'][1]['text']}) or c['answer_bindings'].update({k:['Cshort']}) for k in c['answers'] if k!='P4_04'] ,'flag missing structured KPI context')
Path('rc_attacks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));f.doCleanups()
