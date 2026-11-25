"""Independent synthetic regression; never represents customer or official data."""
import copy, hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrity as I, validate_submission as S, validate_eligibility as V, kb

class Integrity(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup); self.root=Path(self.t.name)
        self.text='示例品牌2025年销售额100元'; self.p=self.root/'data.txt'; self.p.write_text(self.text,encoding='utf-8')
        self.ev={'evidence_id':'E1','file':'data.txt','sha256':I.digest(self.p),'locator':'L1','quote':self.text,'provider':'SYNTHETIC','metric':'销售额','period':'2025','scope':'示例品牌','status':'PENDING_LOCAL_CHECK','confidentiality':'low','publication_cleared':True}
        self.cl={'claim_id':'C1','type':'FACT','text':self.text,'evidence_ids':['E1'],'period':'2025','scope':'示例品牌','value':'100','unit':'元','metric':'销售额'}
        self.doc={'evidence':[self.ev],'claims':[self.cl]}
    def errors(self): return I.evidence_audit(self.doc,self.root)[0]
    def test_exact(self): self.assertEqual(self.errors(),[])
    def test_missing_root(self): self.assertTrue(I.evidence_audit(self.doc,None)[0])
    def test_missing_file(self): self.p.unlink(); self.assertTrue(self.errors())
    def test_missing_status(self): self.ev['status']='MISSING'; self.assertTrue(self.errors())
    def test_missing_sha(self): self.ev.pop('sha256'); self.assertTrue(self.errors())
    def test_hash_mismatch(self): self.p.write_text('other'); self.assertTrue(self.errors())
    def test_unrelated_correct_hash(self): self.p.write_text('unrelated'); self.ev['sha256']=I.digest(self.p); self.assertTrue(self.errors())
    def test_bad_locator(self): self.ev['locator']='L999'; self.assertTrue(self.errors())
    def test_unbound(self): self.cl['evidence_ids']=[]; self.assertTrue(self.errors())
    def test_unsupported_claim(self): self.cl['text']='销量增长999999%'; self.assertTrue(self.errors())
    def test_fabricated_metric_value(self): self.cl['value']='999999'; self.assertTrue(self.errors())
    def test_duplicate(self): self.doc['evidence'].append(copy.deepcopy(self.ev)); self.assertTrue(self.errors())
    def test_scope(self): self.cl['scope']='其他品牌'; self.assertTrue(self.errors())
    def test_traversal(self): self.ev['file']='../data.txt'; self.assertTrue(self.errors())
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'outer.txt';p.write_text(self.text);(self.root/'alias.txt').symlink_to(p);self.ev.update(file='alias.txt',sha256=I.digest(p));self.assertTrue(self.errors())
    def test_calculation(self):
        self.p.write_text('100 | 50');self.ev.update(sha256=I.digest(self.p),quote='100 | 50'); self.cl.update(type='CALC',text='差值50元',value='50',calculation={'operation':'difference','operands':[{'evidence_id':'E1','value':'100'},{'evidence_id':'E1','value':'50'}]});self.assertTrue(self.errors());self.cl['value']='999';self.assertTrue(self.errors()) # V1.1.1: unlabelled operands must now fail; valid calculation covered in new suite
    def test_no_metrics(self): self.assertTrue(I.metric_audit({}, {'C1':self.cl}))
    def test_bad_form(self): self.assertTrue(I.field_audit({'form':'fake','category_numbers':[1],'answers':{}},'EFFIE_GC_MAIN',{}))
    def test_empty_placeholder(self): self.assertTrue(I.field_audit({'form':'通用','category_numbers':[1],'answers':{'B01':'无'}},'EFFIE_GC_MAIN',{}))
    def test_body_injection(self):
        ans={'form':'通用','category_numbers':[1],'answers':{'B01':self.text+'；增长999999%'},'answer_bindings':{'B01':['C1']}};self.assertIn('正文与主张拼接不一致: B01',I.field_audit(ans,'EFFIE_GC_MAIN',{'C1':self.cl}))
    def test_special_unknown(self): self.assertEqual(V.check_category_special({'category_numbers':[29]},'EFFIE_GC_MAIN').status,'CONDITIONAL')
    def test_budget_scope(self): self.assertEqual(V.check_category_special({'category_numbers':[53],'budget_cny':1500000,'has_other_activities_in_period':False},'EFFIE_GC_MAIN').status,'CONDITIONAL')
    def test_year(self): self.assertEqual(V.check_year_covered({},'EFFIE_GC_MAIN').status,'UNKNOWN')
    def test_rules_unverified(self): self.assertIsNone(kb.rule_value('EFFIE_AI_COMMERCE','scoring_weights'))
    def test_placeholder_assets(self): self.assertTrue(I.artifact_audit({'creative_video':{'foo':True},'creative_print':[{}]},'EFFIE_GC_MAIN',self.root)[0])
    def test_duplicate_json(self):
        p=self.root/'bad.json';p.write_text('{"a":1,"a":2}');self.assertRaises(ValueError,S.strict_json,p)
    def test_final_attack(self):
        c={'competition_year':2026,'award_id':'EFFIE_GC_MAIN','form':'fake','category_numbers':[1],'implementation_start':'2025-01-01','implementation_end':'2025-12-31','region':'GREATER_CHINA','has_pilot_only':False,'status':'READY_TO_SUBMIT','authorization':{'client_authorized':True,'agreement_signed':True,'publication_option':'as_submitted'},'evidence':[dict(self.ev,status='MISSING')],'claims':[dict(self.cl,evidence_ids=[])],'creative_video':{'foo':True},'creative_print':[{}],'attribution':{'claimed_conclusion':'A'},'open_p0_issues':[]};o=S.preflight(c,'EFFIE_GC_MAIN',None);self.assertNotEqual(o['status'],S.READY);self.assertTrue({'G04','G05','G06','G08','G11','G10'}.issubset(o['failed_gates']));self.assertFalse(o['submission_authorized'])
    def test_public_leak(self):
        self.ev['confidentiality']='secret';o=S.preflight(dict(self.doc,competition_year=2026,award_id='EFFIE_GC_MAIN'),'EFFIE_GC_MAIN',self.root);self.assertIn('G09',o['failed_gates'])
    def positive_case(self):
        # Deliberately artificial fixture tests reachability, NOT professional quality.
        from PIL import Image
        from docx import Document
        def record(name): return {'file':name,'sha256':I.digest(self.root/name)}
        Image.new('RGB',(16,16),'white').save(self.root/'pic.png')
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=16x16:d=1','-pix_fmt','yuv420p',str(self.root/'v.mp4')],check=True,timeout=20)
        for name in ('auth.docx','agreement.docx'):
            d=Document();d.add_paragraph('SYNTHETIC test only');d.save(self.root/name)
        r={'scope':'示例品牌','period':'2025','metric':'销售额','value':'100','unit':'元','denominator':'全渠道','baseline':'90','baseline_period':'2024','provider':'SYNTHETIC'}
        self.p.write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8'); self.ev.update(sha256=I.digest(self.p),quote=self.p.read_text(encoding='utf-8'))
        self.text=I.render_fact(r);self.cl['text']=self.text
        c=dict(self.doc,competition_year=2026,award_id='EFFIE_GC_MAIN',form='通用',category_numbers=[1],implementation_start='2025-01-01',implementation_end='2025-12-31',region='GREATER_CHINA',has_pilot_only=False)
        c['answers']={f['field_id']:self.text for f in kb.all_fields('通用') if f['required']};c['answer_bindings']={k:['C1'] for k in c['answers']}
        # M03 has a 20-character limit: use a separate complete compact literal.
        p=self.root/'short.txt';short='示例品牌2025年销售额100元';p.write_text(short,encoding='utf-8')
        c['evidence'].append(dict(self.ev,evidence_id='Eshort',file=p.name,sha256=I.digest(p),quote=short))
        c['claims'].append(dict(self.cl,claim_id='Cshort',text=short,evidence_ids=['Eshort']))
        c['answers']['M03']=short;c['answer_bindings']['M03']=['Cshort']
        c['goals']=[{'goal_id':'G1','type':'business','kpi':'销售额'}];c['metrics']=[{'metric_id':'M1','goal_id':'G1','claim_id':'C1','name':'销售额','value':'100','unit':'元','period':'2025','scope':'示例品牌','source':'SYNTHETIC','denominator':'全渠道','baseline':'90','baseline_period':'2024'}]
        c['attribution']={'claimed_conclusion':'C','methods':['pre_post'],'confounders_addressed':['seasonality','category_growth','price_promo','channel_expansion','organic_growth','macro'],'section_4_2_text':c['answers']['P4_04'],'has_parallel_campaigns':False,'evidence_ids':['E1']}
        c['creative_video']=dict(record('v.mp4'),has_agency_name=False);c['creative_print']=[dict(record('pic.png'),has_agency_name=False)];c['authorization']={'client_authorized':True,'agreement_signed':True,'publication_option':'as_submitted','client_authorization_file':record('auth.docx'),'signed_agreement_file':record('agreement.docx')}
        return c
    def test_positive_preflight(self):
        c=self.positive_case()
        out=S.preflight(c,'EFFIE_GC_MAIN',self.root);self.assertEqual(out['status'],S.READY,out['gates']);self.assertFalse(out['submission_authorized']);self.assertTrue(out['human_review_required'])
        c['answers']['P4_04']+=' 未登记';self.assertNotEqual(S.preflight(c,'EFFIE_GC_MAIN',self.root)['status'],S.READY)

if __name__=='__main__': unittest.main(verbosity=2)
