"""V1.1.1 RC attacks; synthetic data only. No independent semantic certification."""
import copy, json, subprocess, sys, unittest
from pathlib import Path
import test_integrity_v11 as fixtures
from test_integrity_v11 import I, S, kb
# Do not discover the imported historical test class twice.
class Semantic(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Integrity(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root=self.f.root
    def pre(self,c): return S.preflight(c,'EFFIE_GC_MAIN',self.root)
    def blocked(self,c,gate):
        o=self.pre(c); self.assertIn(gate,o['failed_gates'],o);self.assertNotEqual(o['status'],S.READY);self.assertFalse(o['submission_authorized'])
    def test_inference_laundering(self):
        c=self.f.positive_case(); c['claims'][0].update(type='INFERENCE',reasoning='因为有数据',text='本次营销直接贡献全部销售额，净利润增长999999%')
        c['answers']={k:c['claims'][0]['text'] for k in c['answers']}; c['attribution']['section_4_2_text']=c['answers']['P4_04']; self.blocked(c,'G05')
    def test_claim_laundering(self):
        c=self.f.positive_case(); c['claims'][0].update(type='CLAIM',reasoning='客户确认'); self.blocked(c,'G05')
    def test_metric_label(self):
        c=self.f.positive_case(); c['metrics'][0]['name']='净利润'; self.blocked(c,'G06')
    def test_unit_relabel(self):
        c=self.f.positive_case(); c['claims'][0]['unit']=c['metrics'][0]['unit']='万元';self.blocked(c,'G05')
    def test_period_relabel(self):
        c=self.f.positive_case();
        for obj in (c['evidence'][0],c['claims'][0],c['metrics'][0]): obj['period']='2024'
        self.blocked(c,'G05')
    def test_scope_relabel(self):
        c=self.f.positive_case();
        for obj in (c['evidence'][0],c['claims'][0],c['metrics'][0]): obj['scope']='其他品牌'
        self.blocked(c,'G05')
    def test_baseline_relabel(self):
        c=self.f.positive_case(); c['metrics'][0]['baseline']='99';self.blocked(c,'G06')
    def test_denominator_relabel(self):
        c=self.f.positive_case(); c['metrics'][0]['denominator']='新用户';self.blocked(c,'G06')
    def test_baseline_period(self):
        c=self.f.positive_case(); c['metrics'][0]['baseline_period']='2023';self.blocked(c,'G06')
    def test_goal_mismatch(self):
        c=self.f.positive_case();c['goals'][0]['kpi']='利润';self.blocked(c,'G06')
    def test_provider_mismatch(self):
        c=self.f.positive_case();c['metrics'][0]['source']='第三方调研';self.blocked(c,'G06')
    def test_fake_pdf(self):
        c=self.f.positive_case();p=self.root/'fake.pdf';p.write_text('not a PDF');c['authorization']['signed_agreement_file']={'file':p.name,'sha256':I.digest(p)};self.blocked(c,'G08')
    def test_fake_docx(self):
        c=self.f.positive_case();p=self.root/'fake.docx';p.write_text('not a DOCX');c['authorization']['client_authorization_file']={'file':p.name,'sha256':I.digest(p)};self.blocked(c,'G08')
    def test_partial_quote(self):
        self.f.p.write_text(self.f.text+'（非实际结果）');self.f.ev['sha256']=I.digest(self.f.p);self.assertTrue(self.f.errors())
    def test_draft_hypothesis_separate(self):
        c=self.f.positive_case();c['draft_hypotheses']=[{'text':'可能由营销驱动，尚待验证'}];out=self.pre(c);self.assertEqual(out['status'],S.READY,out);self.assertFalse(out['submission_authorized'])
    def test_category_scope(self):
        script=Path(I.__file__).with_name('category_query.py');
        other=kb.categories()['other_awards'].get('EFFIE_PRA') or {}; pool=other.get('categories',[])
        for arg in ['--search','--track']:
            r=subprocess.run([sys.executable,str(script),'--award','EFFIE_PRA',arg,'私域'],capture_output=True,text=True,timeout=20)
            self.assertNotIn('EFFIE_GC_MAIN',r.stdout);self.assertNotIn('电竞营销赛道',r.stdout)
            if not pool:self.assertNotEqual(r.returncode,0)
        p=self.root/'case.json';p.write_text(json.dumps({'summary':'私域营销'}),encoding='utf-8');r=subprocess.run([sys.executable,str(script),'--award','EFFIE_PRA','--candidates',str(p)],capture_output=True,text=True,timeout=20)
        if not pool:self.assertNotEqual(r.returncode,0)
    def test_unverified_weights(self):
        p=self.root/'scores.json';p.write_text(json.dumps({k:8 for k in ('part1_challenge','part2_insight_strategy','part3_execution','part4_results')}));r=subprocess.run([sys.executable,str(Path(I.__file__).with_name('calculate_score.py')),'--award','EFFIE_AI_COMMERCE','--scores',str(p),'--json'],capture_output=True,text=True,timeout=20);self.assertNotEqual(r.returncode,0);self.assertNotIn('total',r.stdout)
    def calc_case(self):
        c=self.f.positive_case(); r=json.loads(self.f.ev['quote']); old=dict(r,period='2024',value='90',baseline='80',baseline_period='2023'); p=self.root/'prior.txt';p.write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8'); e=dict(self.f.ev,evidence_id='E2',period='2024',file=p.name,sha256=I.digest(p),quote=p.read_text(encoding='utf-8')); c['evidence'].append(e);cl={'claim_id':'C2','type':'CALC','text':'示例品牌，2025相对2024，销售额差值为10元','evidence_ids':['E1','E2'],'period':'2025','scope':'示例品牌','metric':'销售额差值','unit':'元','value':'10','calculation':{'operation':'difference','operands':[{'evidence_id':'E1','value':'100'},{'evidence_id':'E2','value':'90'}]}};c['claims'].append(cl);return c,cl
    def test_calc_positive(self):
        c,cl=self.calc_case();self.assertFalse(I.evidence_audit(c,self.root)[0])
    def test_calc_injection(self):
        c,cl=self.calc_case();cl['text']+='，利润增长999999%';self.blocked(c,'G05')
    def test_calc_operand_mismatch(self):
        c,cl=self.calc_case();cl['calculation']['operands'][1]['value']='80';self.blocked(c,'G05')
    def test_calc_wrong_unit(self):
        c,cl=self.calc_case();cl['unit']='万元';self.blocked(c,'G05')
    def test_no_unparsed_numeric(self):
        self.f.p.write_text('示例品牌2025年销售额100元，利润未披露');self.f.ev.update(quote=self.f.p.read_text(),sha256=I.digest(self.f.p));self.f.cl.update(text=self.f.ev['quote']);self.assertTrue(self.f.errors())
    def test_standalone_evidence_valid(self):
        c,cl=self.calc_case();p=self.root/'ev.json';p.write_text(json.dumps(c,ensure_ascii=False),encoding='utf-8')
        r=subprocess.run([sys.executable,str(Path(I.__file__).with_name('verify_evidence.py')),'--file',str(p),'--base-dir',str(self.root),'--json'],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertFalse(json.loads(r.stdout)['source_authenticity_verified'])
    def test_full_calc_preflight(self):
        c,cl=self.calc_case();c['metrics'][0].update(claim_id='C2',name=cl['metric'],value=cl['value']);c['goals'][0]['kpi']=cl['metric'];out=self.pre(c);self.assertEqual(out['status'],S.READY,out['gates'])
    def test_record_optional_fields_conflict(self):
        c=self.f.positive_case();c['evidence'][0]['unit']='万元';self.blocked(c,'G05')
    def test_all_status_never_authorizes(self):
        c=self.f.positive_case();c['status']='READY_TO_SUBMIT';out=self.pre(c);self.assertFalse(out['submission_authorized']);self.assertTrue(out['human_review_required'])
if __name__=='__main__':unittest.main(verbosity=2)
