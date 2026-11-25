import sys, unittest, json, copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import human_review as H, integrity as I, validate_submission as S
import test_integrity_v11 as fixtures
class HumanReview(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Integrity();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root
    def case(self):return self.f.positive_case()
    def file(self,name,text):p=self.root/name;p.write_text(text,encoding='utf-8');return {'file':name,'sha256':I.digest(p)}
    def codes(self,c):return {x['code'] for x in H.evidence_findings(c,self.root)+H.business_findings(c,self.root)[0]}
    def test_context(self):
        c=self.case();e=c['evidence'][0];e.update(self.file('context.txt',e['quote']+'\n以上为虚构目标，并非实际结果。'));o=S.preflight(c,'EFFIE_GC_MAIN',self.root);self.assertEqual(o['status'],'BLOCKED');self.assertIn('CONTEXT_WARNING',{x['code'] for x in o['review_findings']})
    def test_conflict(self):
        c=self.case();e=copy.deepcopy(c['evidence'][0]);r=json.loads(e['quote']);r['value']='1';q=json.dumps(r,ensure_ascii=False);e.update(self.file('conflict.txt',q),evidence_id='E2',quote=q);c['evidence'].append(e);self.assertIn('SOURCE_CONFLICT',self.codes(c))
    def test_label(self):
        c=self.case();e=c['evidence'][0];r=json.loads(e['quote']);r['metric']='销量（营销使利润翻倍）';q=json.dumps(r,ensure_ascii=False);e.update(self.file('label.txt',q),metric=r['metric'],quote=q);self.assertIn('LABEL_REVIEW',self.codes(c))
    def test_period(self):
        c=self.case();c['metrics'][0]['period']='2035';self.assertIn('PERIOD_MISMATCH',self.codes(c))
    def test_target_missing(self):self.assertIn('GOAL_REVIEW',self.codes(self.case()))
    def test_target(self):
        c=self.case();g=c['goals'][0];q='示例品牌2025销售额目标至少110元，2024-12-01设定';g.update(target='110',direction='AT_LEAST',unit='元',scope='示例品牌',period='2025',set_date='2024-12-01',target_source=dict(self.file('target.txt',q),locator='L1',quote=q));issues,results=H.business_findings(c,self.root);self.assertEqual(results[0]['comparison'],'NOT_MET');self.assertNotIn('GOAL_REVIEW',{i['code'] for i in issues})
    def test_body(self):
        c=self.case();c['answer_bindings']={k:['Cshort'] for k in c['answers']};self.assertIn('RESULT_NOT_IN_BODY',self.codes(c))
    def test_repeat(self):self.assertIn('FIELD_REPETITION',self.codes(self.case()))
    def test_auth(self):
        c=self.case();a=c['authorization'];a['signed_agreement_file']=a['client_authorization_file'];self.assertIn('DUPLICATE_AUTH',self.codes(c))
    def test_provenance(self):
        c=self.case();o=S.preflight(c,'EFFIE_GC_MAIN',self.root);self.assertEqual(o['dimensions']['evidence_credibility'],'SOURCE_AUTHENTICITY_UNKNOWN');self.assertFalse(o['submission_authorized']);self.assertEqual(o['status'],'HUMAN_REVIEW_REQUIRED')
    def test_natural(self):
        self.file('natural.txt','示例品牌2025年全渠道销售额100元，2024年为90元。');c=H.inventory(self.root,['natural.txt'])['candidates'][0];self.assertEqual(c['status'],'CANDIDATE_ONLY');note=H.review_candidate(self.root,c,'reviewer','ACCEPT_FOR_DRAFT','checked original','销售额100元');self.assertFalse(note['identity_verified']);self.assertFalse(note['submission_authorized'])
    def test_stale(self):
        self.file('a.txt','first');c=H.inventory(self.root,['a.txt'])['candidates'][0];self.file('a.txt','second');self.assertRaises(ValueError,H.review_candidate,self.root,c,'reviewer','ACCEPT_FOR_DRAFT','note','interpretation')
    def test_tamper(self):
        self.file('a.txt','first');c=H.inventory(self.root,['a.txt'])['candidates'][0];c['quote']='fake';self.assertRaises(ValueError,H.review_candidate,self.root,c,'reviewer','ACCEPT_FOR_DRAFT','note','interpretation')
    def test_flag(self):
        self.file('a.txt','销售额100元\n并非实际结果');c=H.inventory(self.root,['a.txt'])['candidates'][0];self.assertRaises(ValueError,H.review_candidate,self.root,c,'reviewer','ACCEPT_FOR_DRAFT','note','interpretation')
    def test_escape(self):self.assertEqual(H.inventory(self.root,['../a.txt'])['files'][0]['status'],'MANUAL_REQUIRED')
    def test_docx(self):
        from docx import Document
        p=self.root/'input.docx';d=Document();d.add_paragraph('strategy');d.add_table(rows=1,cols=1).cell(0,0).text='metric';d.save(p);self.assertEqual(len(H.inventory(self.root,[p.name])['candidates']),2)
    def test_pptx(self):
        from pptx import Presentation
        from pptx.util import Inches
        p=self.root/'input.pptx';r=Presentation();s=r.slides.add_slide(r.slide_layouts[6]);s.shapes.add_textbox(Inches(1),Inches(1),Inches(2),Inches(1)).text='strategy';r.save(p);self.assertEqual(H.inventory(self.root,[p.name])['candidates'][0]['locator'],'slide:1')
    def test_xlsx(self):
        from openpyxl import Workbook
        p=self.root/'input.xlsx';w=Workbook();w.active.append(['sales',100,'=B1*2']);w.save(p);c=H.inventory(self.root,[p.name])['candidates'][0];self.assertIn('FORMULA_REVIEW',c['flags'])
    def test_export(self):
        c={'answers':{'B01':'示例名称','P4_01':'实际结果'}};p=self.root/'review.docx';H.export_review(c,p);self.assertEqual(H.final_compare(c,self.root,{'file':p.name,'sha256':I.digest(p)})['status'],'EXACT_TEXT_MATCH_ONLY')
    def test_export_mutated(self):
        from docx import Document
        c={'answers':{'B01':'示例名称'}};p=self.root/'review.docx';H.export_review(c,p);d=Document(p);d.add_paragraph('unregistered text');d.save(p);self.assertRaises(ValueError,H.final_compare,c,self.root,{'file':p.name,'sha256':I.digest(p)})
    def test_no_auth(self):
        c=self.case();c.update(status='READY_TO_SUBMIT',review_approved=True);o=S.preflight(c,'EFFIE_GC_MAIN',self.root);self.assertFalse(o['submission_authorized']);self.assertEqual(o['dimensions']['professional_competitiveness'],'NOT_ASSESSED_BY_MACHINE')
