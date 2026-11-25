"""Local, untrusted review workbench. No source authentication, trusted signatures or submission authorization."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from datetime import date
from collections import defaultdict
import integrity as I
import kb

LIMIT=2000
NEG=re.compile(r'并非实际|非实际结果|虚构|模拟数据|仅供演示|预测值|目标值|尚未实现|未实现|not actual|hypothetical|forecast|illustrative|fictional',re.I)
LABEL=re.compile(r'[（）()【】\[\]：:，,。！？!?；;\n]|翻倍|归因|贡献|导致|caused|attributable',re.I)

def sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def file_at(root,name):
    base=Path(root).resolve(strict=True)
    if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe path')
    p=(base/name).resolve(strict=True)
    if not p.is_relative_to(base) or not p.is_file() or not 0<p.stat().st_size<=I.MAX_BYTES: raise ValueError('invalid file')
    return p

def blocks(p):
    ext=p.suffix.lower()
    if ext in {'.txt','.md','.csv','.jsonl'}:
        for i,s in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1): yield f'L{i}',s
    elif ext=='.pdf':
        from pypdf import PdfReader
        for i,page in enumerate(PdfReader(p).pages,1): yield f'p.{i}',page.extract_text() or ''
    elif ext=='.docx':
        from docx import Document
        d=Document(p)
        for i,para in enumerate(d.paragraphs,1): yield f'paragraph:{i}',para.text
        for t,table in enumerate(d.tables,1):
            for r,row in enumerate(table.rows,1): yield f'table:{t}:row:{r}',' | '.join(c.text for c in row.cells)
    elif ext=='.xlsx':
        from openpyxl import load_workbook
        w=load_workbook(p,read_only=True,data_only=False)
        try:
            for s in w:
                if (s.max_column or 0)>256: raise ValueError('wide sheet needs manual inspection')
                for n,row in enumerate(s.iter_rows(max_col=s.max_column),1):
                    yield f'{s.title}!A{n}:{row[-1].column_letter if hasattr(row[-1],"column_letter") else __import__("openpyxl").utils.get_column_letter(len(row))}{n}', ' | '.join('[FORMULA] '+str(c.value) if c.data_type=='f' else '' if c.value is None else str(c.value) for c in row)
        finally: w.close()
    elif ext=='.pptx':
        from pptx import Presentation
        for i,slide in enumerate(Presentation(p).slides,1):
            parts=[]
            for shape in slide.shapes:
                if shape.has_text_frame: parts.append(shape.text)
                if shape.has_table: parts.extend(' | '.join(c.text for c in r.cells) for r in shape.table.rows)
            yield f'slide:{i}','\n'.join(parts)
    else: raise ValueError('unsupported format; manual review')

def inventory(root,names):
    output=[]; candidates=[]
    for name in dict.fromkeys(names):
        rec={'file':name,'status':'MANUAL_REQUIRED','source_authenticity':'UNKNOWN'}
        try:
            p=file_at(root,name); rec['sha256']=I.digest(p); rows=[]
            for i,(loc,raw) in enumerate(blocks(p)):
                if i>=LIMIT: rec['truncated']=True; break
                if len(raw)>20000: rec['truncated']=True; continue
                rows.append((loc,raw))
            for i,(loc,raw) in enumerate(rows):
                if not raw.strip(): continue
                context='\n'.join(x[1] for x in rows[max(0,i-1):i+2]); item={'file':name,'sha256':rec['sha256'],'locator':loc,'quote':raw,'context':context,'flags':(['NON_ACTUAL_OR_CONTEXT_REVIEW'] if NEG.search(context) else [])+(['FORMULA_REVIEW'] if '[FORMULA]' in context else [])}
                item['candidate_id']=sha(item); item['status']='CANDIDATE_ONLY'; candidates.append(item)
            rec['status']='PARTIAL' if rec.get('truncated') else 'EXTRACTED_CANDIDATES' if any(x[1].strip() for x in rows) else 'NO_TEXT'
        except Exception as ex: rec['error']=str(ex)
        output.append(rec)
    return {'files':output,'candidates':candidates,'submission_authorized':False,'notice':'Candidates are not verified facts; images/charts/layout and source authenticity require human inspection.'}

def review_candidate(root,candidate,reviewer,decision,note,interpretation):
    if decision not in {'ACCEPT_FOR_DRAFT','REJECT','NEEDS_EVIDENCE'} or not all(I.meaningful(x) for x in (reviewer,note)): raise ValueError('decision, reviewer and rationale required')
    fresh=inventory(root,[candidate['file']]); matches=[c for c in fresh['candidates'] if c['candidate_id']==candidate['candidate_id']]
    if len(matches)!=1 or candidate!=matches[0]: raise ValueError('candidate stale or altered')
    if decision=='ACCEPT_FOR_DRAFT' and candidate['flags']: raise ValueError('flagged candidate needs separate evidence or rejection; cannot accept as draft fact')
    return {'candidate_id':candidate['candidate_id'],'candidate':candidate,'reviewer_label':reviewer,'decision':decision,'note':note,'interpretation':interpretation,'identity_verified':False,'source_authenticity':'UNKNOWN','record_kind':'LOCAL_REVIEW_NOTE_ONLY','submission_authorized':False}

def period_range(s):
    if not isinstance(s,str): raise ValueError('period must be a string')
    if re.fullmatch(r'\d{4}',s): return date(int(s),1,1),date(int(s),12,31)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s): d=date.fromisoformat(s);return d,d
    a,b=s.split('/')
    a,b=date.fromisoformat(a),date.fromisoformat(b)
    if a>b: raise ValueError('reversed period')
    return a,b

def evidence_findings(case,root):
    out=[]; groups=defaultdict(list)
    def issue(code,ref,detail,severity='BLOCK'):out.append({'code':code,'ref':ref,'detail':detail,'severity':severity})
    for e in case.get('evidence') or []:
        if not isinstance(e,dict): continue
        eid=e.get('evidence_id','?')
        try:
            p=I.resolve_file(root,e); raw=I.extract(p,e['locator']); r=I.parse_source_record(raw,e)
            # Complete bounded document scan for caution terms; not an entailment engine.
            found=False; incomplete=False
            for i,(loc,text) in enumerate(blocks(p)):
                if i>=LIMIT: incomplete=True;break
                if NEG.search(text): found=True
            if found: issue('CONTEXT_WARNING',eid,'原件存在目标/预测/否定性提示；不得仅凭局部引用判断实际结果')
            if incomplete: issue('CONTEXT_INCOMPLETE',eid,'原件超出自动上下文扫描范围','REVIEW')
            if r and 'literal' not in r:
                for k in ('metric','scope','unit','denominator','provider'):
                    if LABEL.search(r[k]): issue('LABEL_REVIEW',eid,f'{k} 含叙述或异常标点，须核查语义')
                key=tuple(I.norm(r[k]).casefold() for k in ('scope','period','metric','unit','denominator'))
                groups[key].append((eid,I.dec(r['value']),I.dec(r['baseline']),r['baseline_period']))
        except Exception as ex: issue('SOURCE_REVIEW',eid,str(ex),'REVIEW')
    for key,rs in groups.items():
        if len({(r[1],r[2],r[3]) for r in rs})>1: issue('SOURCE_CONFLICT',','.join(r[0] for r in rs),'同口径源记录相互矛盾；保留全部来源，不自动选优')
    return out

def business_findings(case,root):
    out=[]; completion=[]
    def issue(code,ref,detail,severity='BLOCK'):out.append({'code':code,'ref':ref,'detail':detail,'severity':severity})
    goals=case.get('goals') or []; metrics=case.get('metrics') or []; answers=case.get('answers') or {}; bindings=case.get('answer_bindings') or {}
    if not isinstance(goals,list) or not isinstance(metrics,list) or not isinstance(answers,dict) or not isinstance(bindings,dict): return [{'code':'INPUT','ref':'case','detail':'invalid business inputs','severity':'BLOCK'}],[]
    try: start=date.fromisoformat(case['implementation_start']);end=date.fromisoformat(case['implementation_end'])
    except Exception: start=end=None
    for m in metrics:
        if not isinstance(m,dict):continue
        mid=m.get('metric_id','?')
        try:
            a,b=period_range(m['period'])
            if not start or not end or b<start or a>end: issue('PERIOD_MISMATCH',mid,'成果期间与活动实施期间不重叠；延迟效果须另走人工归因')
            elif a<start or b>end: issue('PERIOD_PARTIAL',mid,'成果统计期间超出活动期间，需审查口径','REVIEW')
        except Exception: issue('PERIOD_UNKNOWN',mid,'无法解释成果统计期间','REVIEW')
    for g in goals:
        if not isinstance(g,dict):continue
        gid=g.get('goal_id','?')
        try:
            target=I.dec(g['target']);direction=g['direction'];unit=g['unit']; scope=g['scope'];period=g['period']
            if direction not in {'AT_LEAST','AT_MOST'} or not all(I.meaningful(x) for x in (unit,scope,period)):raise ValueError('target contract missing')
            # Separate target provenance from result. Exact quote is a local check only.
            t=g['target_source'];p=I.resolve_file(root,t);raw=I.extract(p,t['locator']);
            if I.norm(raw)!=I.norm(t['quote']):raise ValueError('target source mismatch')
            # Exact numeric token, unit, declared direction and setting date; still not source authentication.
            target_pattern=r'(?:目标|target)\s*(?:至少|不低于|at least|至多|不高于|at most)\s*'+re.escape(str(g['target']))+re.escape(unit)+r'(?![\d.])'
            if not re.search(target_pattern,raw,re.I) or not all(str(x) in raw for x in (g['kpi'],scope,period,g['set_date'])):raise ValueError('target source fields not locally visible')
            if direction=='AT_LEAST' and not re.search(r'目标\s*(?:至少|不低于)|target\s*at least',raw,re.I):raise ValueError('target direction mismatch')
            if direction=='AT_MOST' and not re.search(r'目标\s*(?:至多|不高于)|target\s*at most',raw,re.I):raise ValueError('target direction mismatch')
            if not start or date.fromisoformat(g['set_date'])>start:raise ValueError('goal not set before campaign')
            ms=[m for m in metrics if isinstance(m,dict) and m.get('goal_id')==gid]
            for m in ms:
                if any(m.get(k)!=g[k] for k in ('unit','scope','period')) or m.get('name')!=g.get('kpi'):raise ValueError('target/result scope mismatch')
                v=I.dec(m['value']);completion.append({'goal_id':gid,'metric_id':m['metric_id'],'target':str(target),'actual':str(v),'unit':unit,'comparison':'MET' if (v>=target if direction=='AT_LEAST' else v<=target) else 'NOT_MET','status':'LOCAL_COMPARISON_ONLY'})
            if not ms:raise ValueError('no result')
        except Exception as ex:issue('GOAL_REVIEW',gid,str(ex),'REVIEW')
    # Detect extreme repetition and missing results, not general semantic scoring.
    bytext=defaultdict(list)
    for fid,val in answers.items():
        if isinstance(val,str) and val.strip():bytext[I.norm(val)].append(fid)
    for v,fids in bytext.items():
        if len(fids)>=5:issue('FIELD_REPETITION',','.join(fids),'多个不同业务字段重复同一内容，需按字段补齐','REVIEW')
    result_ids={m.get('claim_id') for m in metrics if isinstance(m,dict)}
    result_fields=[k for k in bindings if k=='E05' or k=='P4_01' or re.fullmatch(r'P4_02[a-c]\d*',k)]
    for cid in result_ids:
        if not any(isinstance(bindings[k],list) and cid in bindings[k] for k in result_fields):issue('RESULT_NOT_IN_BODY',str(cid),'成果未进入对应成果正文','REVIEW')
    auth=case.get('authorization') or {}
    if isinstance(auth,dict):
        x=auth.get('client_authorization_file') or {};y=auth.get('signed_agreement_file') or {}
        if isinstance(x,dict) and isinstance(y,dict) and x.get('sha256') and x.get('sha256')==y.get('sha256'):issue('DUPLICATE_AUTH','authorization','两种授权角色引用同一内容，须核验覆盖范围','REVIEW')
    return out,completion

def final_compare(case,root,record):
    """Exact comparison for our review copy format, NOT official form or arbitrary DOCX."""
    from docx import Document
    p=I.resolve_file(root,record)
    if p.suffix.lower()!='.docx':raise ValueError('only tagged review DOCX supported')
    d=Document(p); seen={}
    # Reject unsupported containers rather than silently ignoring them.
    if d.tables or d.inline_shapes or any(s.header.paragraphs[0].text or s.footer.paragraphs[0].text for s in d.sections):raise ValueError('unsupported document content')
    from zipfile import ZipFile
    with ZipFile(p) as z:
        from lxml import etree
        xml=etree.fromstring(z.read('word/document.xml')); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        if xml.xpath('//w:ins|//w:del|//w:txbxContent|//w:hyperlink|//w:fldSimple|//w:instrText|//w:drawing|//w:object|//w:sdt',namespaces=ns):raise ValueError('unsupported embedded or revised content')
        if any(re.match(r'word/(header|footer|footnotes|endnotes|comments|media/)',n) for n in z.namelist()):raise ValueError('unsupported auxiliary document content')
    for para in d.paragraphs:
        m=re.fullmatch(r'\[([A-Z0-9_]+)\] ([\s\S]+)',para.text)
        if not m or m[1] in seen:raise ValueError('untagged or duplicate paragraph')
        seen[m[1]]=m[2]
    expected=case.get('answers') or {}
    if seen!=expected:raise ValueError('document fields differ from case answers')
    return {'status':'EXACT_TEXT_MATCH_ONLY','sha256':record['sha256'],'field_count':len(seen),'official_form_verified':False}

def export_review(case,path):
    from docx import Document
    d=Document()
    for k,v in (case.get('answers') or {}).items():
        if not re.fullmatch(r'[A-Z0-9_]+',k) or not isinstance(v,str):raise ValueError('invalid field')
        d.add_paragraph(f'[{k}] {v}')
    d.save(path)

def assess(case,root,technical):
    try: ev=evidence_findings(case,root); biz,completion=business_findings(case,root)
    except Exception as ex: ev=[{'code':'REVIEW_ERROR','ref':'case','detail':str(ex),'severity':'BLOCK'}];biz=[];completion=[]
    try: final=final_compare(case,root,case['final_review_file'])
    except Exception as ex: final={'status':'REVIEW_REQUIRED','detail':str(ex)}
    notes=[]
    for n in case.get('review_notes') or []:
        try:
            if not isinstance(n,dict):raise ValueError('invalid review note')
            fresh=review_candidate(root,n['candidate'],n['reviewer_label'],n['decision'],n['note'],n['interpretation'])
            if fresh!=n:raise ValueError('altered review note')
            notes.append({'candidate_id':fresh['candidate_id'],'decision':fresh['decision'],'identity_verified':False,'status':'DRAFT_NOTE_ONLY'})
        except Exception as ex:biz.append({'code':'REVIEW_NOTE_INVALID','ref':'review_notes','detail':str(ex),'severity':'REVIEW'})
    hard=any(i['severity']=='BLOCK' for i in ev+biz)
    technical_pass=not technical['failed_gates']
    dimensions={'technical_consistency':'PASS_LOCAL_ONLY' if technical_pass else 'FAIL_OR_UNKNOWN','evidence_credibility':'CONFLICT_OR_REVIEW' if ev else 'SOURCE_AUTHENTICITY_UNKNOWN','professional_competitiveness':'NOT_ASSESSED_BY_MACHINE','delivery_compliance':'REVIEW_REQUIRED','final_document':final['status']}
    status='BLOCKED' if hard or technical['status']=='BLOCKED' else 'HUMAN_REVIEW_REQUIRED' if technical_pass else 'NEEDS_EVIDENCE'
    technical.update(status=status,technical_status='PASS_LOCAL_ONLY' if technical_pass else 'FAIL_OR_UNKNOWN',dimensions=dimensions,review_findings=ev+biz,goal_comparisons=completion,review_notes_checked=notes,final_document=final,submission_authorized=False)
    return technical

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('intake');a.add_argument('--base-dir',required=True);a.add_argument('files',nargs='+')
    a=sub.add_parser('review');a.add_argument('--base-dir',required=True);a.add_argument('--candidate',required=True);a.add_argument('--reviewer',required=True);a.add_argument('--decision',required=True);a.add_argument('--note',required=True);a.add_argument('--interpretation',default='')
    a=sub.add_parser('export-review');a.add_argument('--case',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('compare');a.add_argument('--case',required=True);a.add_argument('--base-dir',required=True);a.add_argument('--file',required=True)
    args=p.parse_args();from validate_submission import strict_json
    try:
        if args.cmd=='intake':out=inventory(args.base_dir,args.files)
        elif args.cmd=='review':out=review_candidate(args.base_dir,strict_json(args.candidate),args.reviewer,args.decision,args.note,args.interpretation)
        elif args.cmd=='export-review':export_review(strict_json(args.case),args.out);out={'status':'REVIEW_COPY_ONLY','file':args.out}
        else:
            f=file_at(args.base_dir,args.file);out=final_compare(strict_json(args.case),args.base_dir,{'file':args.file,'sha256':I.digest(f)})
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as ex:print(json.dumps({'status':'BLOCKED','error':str(ex),'submission_authorized':False},ensure_ascii=False));return 1
if __name__=='__main__':sys.exit(main())
