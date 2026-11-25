"""V1.1 controlled preflight. Conservative V1.1.1 source-record binding; local content match != provenance or semantic proof.
Only deterministic exact extracts are automatically matched; human review remains mandatory.
"""
from __future__ import annotations
import hashlib, json, math, re, subprocess, unicodedata
from pathlib import Path
from decimal import Decimal, InvalidOperation
import kb

MAX_BYTES = 100 * 1024 * 1024
PLACEHOLDERS = {'无','暂无','待补','待确认','未知','不详','n/a','na','none','null','tbd','todo','-','/','示例','placeholder','test'}
def meaningful(x):
    return isinstance(x,str) and bool(x.strip()) and x.strip().lower() not in PLACEHOLDERS

def norm(x):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC',str(x))).strip()

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def resolve_file(root, record):
    if not root or not isinstance(record,dict): raise ValueError('缺材料目录或文件登记')
    base=Path(root).resolve(strict=True)
    name=record.get('file'); sha=record.get('sha256')
    if not meaningful(name) or Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('非法相对路径')
    p=(base/name).resolve(strict=True)
    if not p.is_relative_to(base) or not p.is_file(): raise ValueError('文件不在材料目录')
    if not 0<p.stat().st_size<=MAX_BYTES: raise ValueError('空文件或超出100MiB预检限制')
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or digest(p)!=sha: raise ValueError('缺失或不匹配 SHA-256')
    return p

def extract(p,loc):
    ext=p.suffix.lower()
    if ext in {'.txt','.md','.csv'}:
        m=re.fullmatch(r'L([1-9]\d*)(?:-L?([1-9]\d*))?',loc)
        if not m: raise ValueError('文本定位须 L1 或 L1-L3')
        lines=p.read_text(encoding='utf-8-sig').splitlines(); a=int(m[1]); b=int(m[2] or a)
        if not 1<=a<=b<=len(lines) or b-a>100: raise ValueError('行号越界')
        return '\n'.join(lines[a-1:b])
    if ext=='.pdf':
        from pypdf import PdfReader
        m=re.fullmatch(r'p\.([1-9]\d*)',loc)
        if not m: raise ValueError('PDF定位须 p.1')
        r=PdfReader(p); i=int(m[1]);
        if i>len(r.pages): raise ValueError('页码越界')
        return r.pages[i-1].extract_text() or ''
    if ext=='.docx':
        from docx import Document
        m=re.fullmatch(r'paragraph:([1-9]\d*)',loc)
        if not m: raise ValueError('DOCX定位须 paragraph:1')
        paragraphs=Document(p).paragraphs; i=int(m[1])
        if i>len(paragraphs): raise ValueError('段落越界')
        return paragraphs[i-1].text
    if ext=='.xlsx':
        from openpyxl import load_workbook
        from openpyxl.utils.cell import range_boundaries
        sheet,sep,cell=loc.rpartition('!')
        if not sep or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d*(?::[A-Z]{1,3}[1-9]\d*)?',cell): raise ValueError('XLSX定位须 Sheet1!A1:B2')
        a,b,c,d=range_boundaries(cell)
        if not (a<=c and b<=d and (c-a+1)*(d-b+1)<=1000): raise ValueError('范围过大或反向')
        w=load_workbook(p,read_only=True,data_only=False)
        try:
            s=w[sheet]
            if d>s.max_row or c>s.max_column: raise ValueError('单元格越界')
            rows=[]
            for row in s.iter_rows(min_row=b,max_row=d,min_col=a,max_col=c):
                if any(x.data_type=='f' for x in row): raise ValueError('公式须另附可验证的计算结果，不读取缓存作为事实')
                rows.append(' | '.join('' if x.value is None else str(x.value) for x in row))
            return '\n'.join(rows)
        finally: w.close()
    raise ValueError('格式暂不支持自动定位；需要人工核验')

def unique_records(records,key):
    if not isinstance(records,list) or not records: raise ValueError(f'{key} 列表为空或类型错误')
    out={}
    for r in records:
        if not isinstance(r,dict) or not meaningful(r.get(key)) or r[key] in out: raise ValueError(f'{key} 缺失或重复')
        out[r[key]]=r
    return out

def evidence_audit(case,root):
    errors=[]; matched={}; claims={}
    try: ev=unique_records(case.get('evidence'),'evidence_id'); claims=unique_records(case.get('claims'),'claim_id')
    except ValueError as e: return [str(e)],matched,claims
    for eid,e in ev.items():
        try:
            if e.get('status') in {'MISSING','CONTRADICTED','USER_ASSERTED','UNVERIFIED','PARTIALLY_SUPPORTED'}: raise ValueError('证据状态未达到完整支持')
            if e.get('status') not in {'VERIFIED','PENDING_LOCAL_CHECK'}: raise ValueError('非法证据状态')
            for k in ('provider','metric','period','scope','locator','quote'):
                if not meaningful(e.get(k)): raise ValueError('缺 '+k)
            if e.get('confidentiality') not in {'low','medium','high','secret'}: raise ValueError('缺有效保密等级')
            if type(e.get('publication_cleared')) is not bool: raise ValueError('缺公开权限声明')
            p=resolve_file(root,e); raw=extract(p,e['locator']); q=norm(e['quote'])
            if not q or q != norm(raw): raise ValueError('引用须完整覆盖定位内容，不得截取脱离上下文的片段')
            source=parse_source_record(raw,e)
            matched[eid]={'quote':q,'sha256':e['sha256'],'record':e,'source':source}
        except Exception as ex: errors.append(f'{eid}: {type(ex).__name__}: {ex}')
    for cid,c in claims.items():
        ids=c.get('evidence_ids'); text=c.get('text')
        if not meaningful(text) or c.get('type') not in {'FACT','CALC','CLAIM','INFERENCE'} or not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in matched for i in ids) or len(ids)!=len(set(ids)):
            errors.append(f'{cid}: 主张类型/文本/已匹配证据绑定不完整'); continue
        if c.get('supports') is False: errors.append(f'{cid}: 已声明证据不支持')
        for field in ('period','scope'):
            if not meaningful(c.get(field)) or (not (field=='period' and c.get('type')=='CALC') and any(c[field]!=matched[i]['record'].get(field) for i in ids)): errors.append(f'{cid}: {field} 缺失或冲突')
        # Type labels are not evidence. Only literal facts and constrained calculations
        # belong in the preflight registry; draft hypotheses are outside answers.
        if c['type'] in {'CLAIM','INFERENCE'}:
            errors.append(f'{cid}: 未证声明/推断仅可进入 draft_hypotheses，不得进入正式主张登记'); continue
        if strong_causal(text): errors.append(f'{cid}: 强因果/夸张表达须独立人工审查，不进入自动预检')
        if c['type']=='FACT':
            if len(ids)!=1: errors.append(f'{cid}: FACT 必须绑定唯一完整来源记录'); continue
            e=matched[ids[0]]; source=e['source']
            if source:
                try:
                    if norm(text)!=norm(render_fact(source)): raise ValueError('事实正文必须为源记录的确定性表达')
                    for k in ('metric','period','scope','unit'):
                        if c.get(k)!=source[k]: raise ValueError('主张与原始记录 '+k+' 不一致')
                    if dec(c.get('value'))!=dec(source['value']): raise ValueError('原始记录数值不一致')
                except Exception as ex: errors.append(f'{cid}: {ex}')
            else:
                if norm(text)!=e['quote']: errors.append(f'{cid}: 非结构事实仅接受完整原文逐字对应')
                if c.get('value') is not None or c.get('unit') is not None or re.search(r'\d',text): errors.append(f'{cid}: 数字事实需可解析原始记录；不接受自报数字或单位')
                for k in ('scope','period'):
                    if c.get(k) and str(c[k]) not in text: errors.append(f'{cid}: 原文未体现 {k}；待人工核验')
        elif c['type']=='CALC': errors.extend(check_calc(cid,c,matched))
    return errors,matched,claims

def dec(v):
    if isinstance(v,bool) or not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',str(v)): raise ValueError('仅接受有限十进制数字')
    x=Decimal(str(v));
    if not x.is_finite() or abs(x)>Decimal('1e18'): raise ValueError('数值越界')
    return x

# The parser accepts a complete native JSON record, or the legacy compact single
# observation. Transcribed/forged source files are NOT independently authenticated.
RECORD_KEYS={'scope','period','metric','value','unit','denominator','baseline','baseline_period','provider'}
def strong_causal(text):
    return bool(re.search(r'直接贡献|全部归功|完全归因|唯一原因|100%归因|必然导致|保证增长|directly caused|sole cause|entirely attributable',str(text),re.I))

def parse_source_record(raw,e):
    raw=raw.strip()
    if raw.startswith('{'):
        def pairs(seq):
            d={}
            for k,v in seq:
                if k in d: raise ValueError('源记录重复键')
                d[k]=v
            return d
        r=json.loads(raw,object_pairs_hook=pairs)
        if not isinstance(r,dict) or set(r)!=RECORD_KEYS: raise ValueError('源记录必须为完整单条指标记录')
        if not all(meaningful(r[k]) for k in ('scope','period','metric','unit','denominator','provider','baseline_period')): raise ValueError('源记录口径不完整')
        for k in ('scope','period','metric','unit','denominator','provider','baseline_period'):
            if len(r[k])>160 or re.search(r'[\r\n|；;]',r[k]) or strong_causal(r[k]): raise ValueError('源记录字段含异常内容')
        dec(r['value']); dec(r['baseline'])
        if r['baseline_period']==r['period']: raise ValueError('基线期间须明确且不同于结果期间')
        for k in ('scope','period','metric','provider'):
            if e.get(k)!=r[k]: raise ValueError('证据登记与原始记录 '+k+' 不一致')
        for k in ('unit','denominator','baseline_period'):
            if k in e and e[k]!=r[k]: raise ValueError('证据登记与原始记录 '+k+' 不一致')
        for k in ('value','baseline'):
            if k in e and dec(e[k])!=dec(r[k]): raise ValueError('证据登记与原始记录 '+k+' 不一致')
        return r
    # A fully anchored, compact Chinese observation is supported for literal facts,
    # but cannot satisfy the final KPI gate without source denominator/baseline.
    m=re.fullmatch(re.escape(e['scope'])+re.escape(e['period'])+r'年?'+re.escape(e['metric'])+r'([+-]?\d+(?:\.\d+)?)(元|万元|亿元|%|个百分点|人|件|次)',raw)
    if m:
        dec(m[1]); return {'scope':e['scope'],'period':e['period'],'metric':e['metric'],'value':m[1],'unit':m[2],'literal':raw}
    return None

def render_fact(r):
    if 'literal' in r: return r['literal']
    return f"{r['scope']}，{r['period']}，{r['metric']}为{r['value']}{r['unit']}（分母：{r['denominator']}；基线：{r['baseline_period']} {r['baseline']}{r['unit']}）"

def check_calc(cid,c,matched):
    try:
        op=c.get('calculation') or {}; args=op.get('operands'); kind=op.get('operation')
        if not isinstance(args,list) or len(args)!=2 or kind not in {'difference','growth_pct'}: raise ValueError('自动预检仅支持同口径跨期差值/增长率；其他计算走人工复核')
        vals=[]; records=[]; ids=[]
        for a in args:
            eid=a['evidence_id']; e=matched[eid]; r=e['source']
            if eid not in c['evidence_ids'] or not r or 'literal' in r: raise ValueError('操作数必须绑定完整结构化原始记录')
            if dec(a['value'])!=dec(r['value']): raise ValueError('操作数与原始数值不一致')
            vals.append(dec(r['value'])); records.append(r); ids.append(eid)
        if len(set(ids))!=2 or set(ids)!=set(c['evidence_ids']): raise ValueError('操作数须分别绑定两条唯一来源')
        x,y=vals; cur,base=records
        for k in ('scope','metric','unit','denominator','provider'):
            if cur[k]!=base[k]: raise ValueError('操作数 '+k+' 不一致')
        if cur['period']==base['period'] or cur['baseline_period']!=base['period'] or dec(cur['baseline'])!=y: raise ValueError('基线期间/数值与独立记录不一致')
        result=x-y if kind=='difference' else (x-y)/y*100
        if kind=='difference' and cur['unit'] in {'%','百分点','个百分点'}: raise ValueError('比例差值须明确百分点语义，当前转人工核验')
        unit=cur['unit'] if kind=='difference' else '%' 
        label='差值' if kind=='difference' else '增长率'
        if kind=='growth_pct' and (y<=0 or cur['unit'] in {'%','个百分点'}): raise ValueError('非正基线或比例指标增长须人工复核')
        if abs(result-dec(c.get('value')))>Decimal('0.000001'): raise ValueError('计算结果不匹配')
        for k,v in {'scope':cur['scope'],'period':cur['period'],'metric':cur['metric']+label,'unit':unit}.items():
            if c.get(k)!=v: raise ValueError('计算主张 '+k+' 不一致')
        expected=f"{cur['scope']}，{cur['period']}相对{base['period']}，{cur['metric']}{label}为{c['value']}{unit}"
        if norm(c['text'])!=norm(expected): raise ValueError('计算正文必须使用确定性表达，不得夹带其他主张')
        return []
    except Exception as e: return [f'{cid}: 计算核验失败: {e}']

def field_audit(case,award,claims):
    issues=[]; answers=case.get('answers'); form=case.get('form'); nums=case.get('category_numbers') or []
    if award!='EFFIE_GC_MAIN': return ['专项奖项缺完整专用表映射，仅支持咨询预检']
    if len(nums)!=1: issues.append('每份正式材料仅绑定一个类别；多类别需独立文件')
    expected='通用'
    for n in nums:
        for sr in (kb.get_category(n,award) or {}).get('special_rules',[]):
            if sr['rule']=='dedicated_form': expected=sr['value']
    if form!=expected or form!='通用': issues.append('表单不匹配或专用表完整性未确认；暂不签发预检通过')
    if not isinstance(answers,dict): return issues+['answers 必须是对象']
    fs={f['field_id']:f for f in kb.all_fields(form='通用')}
    import check_word_limits as CWL
    for fid,f in fs.items():
        if f['required'] and not meaningful(answers.get(fid)): issues.append('必填缺失/占位: '+fid)
    bindings=case.get('answer_bindings') or {}
    if not isinstance(bindings,dict): return issues+['answer_bindings 必须是对象']
    for fid,val in answers.items():
        if fid not in fs or not meaningful(val): issues.append('非法字段/占位: '+fid); continue
        limit=fs[fid]['word_limit']
        if limit and CWL.count_chars(val)>limit: issues.append('字段超限: '+fid)
        if re.search(r'https?://|www\.',val,re.I): issues.append('正文外链: '+fid)
        # Whole-field reconstruction: no invisible free-text outside registered segments.
        ids=bindings.get(fid)
        if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in claims for i in ids): issues.append('正文未完整绑定: '+fid); continue
        if norm(val)!=norm(' '.join(claims[i]['text'] for i in ids)): issues.append('正文与主张拼接不一致: '+fid)
    if set(bindings)-set(answers): issues.append('存在孤立正文绑定')
    return issues

def metric_audit(case,claims,matched=None):
    errors=[]
    try: goals=unique_records(case.get('goals'),'goal_id'); metrics=unique_records(case.get('metrics'),'metric_id')
    except ValueError as e: return [str(e)]
    used=set(); matched=matched or {}
    for mid,m in metrics.items():
        gid=m.get('goal_id'); cid=m.get('claim_id'); c=claims.get(cid,{})
        if gid not in goals: errors.append(f'{mid}: 无对应目标')
        else: used.add(gid)
        if not c or c.get('type') not in {'FACT','CALC'}: errors.append(f'{mid}: 未绑定事实/计算主张')
        for k in ('value','unit','period','scope'):
            if m.get(k) is None or str(m.get(k))!=str(c.get(k)): errors.append(f'{mid}: 指标与主张 {k} 不一致')
        try: dec(m.get('value'))
        except ValueError as e: errors.append(f'{mid}: {e}')
        if not all(meaningful(m.get(k)) for k in ('name','source','denominator')): errors.append(f'{mid}: 指标口径缺失')
        if m.get('name')!=c.get('metric') or (gid in goals and goals[gid].get('kpi')!=m.get('name')): errors.append(f'{mid}: 指标名称/目标KPI/主张不一致')
        try:
            ids=c.get('evidence_ids') or []
            eid=ids[0] if c.get('type')=='FACT' else c['calculation']['operands'][0]['evidence_id']
            r=matched[eid]['source']
            if not r or 'literal' in r: raise ValueError('指标必须绑定完整原始记录，缺分母/基线不得自动通过')
            for mk,rk in [('source','provider'),('denominator','denominator'),('baseline_period','baseline_period')]:
                if m.get(mk)!=r[rk]: raise ValueError('指标 '+mk+' 与原始记录不一致')
            if dec(m.get('baseline'))!=dec(r['baseline']): raise ValueError('指标基线与原始记录不一致')
        except Exception as ex: errors.append(f'{mid}: {ex}')
    for gid,g in goals.items():
        if gid not in used or not meaningful(g.get('kpi')): errors.append(f'{gid}: 目标无成果或KPI')
    return errors

def artifact_audit(case,award,root):
    errors=[]; files={}
    def file(rec,kind):
        try:
            p=resolve_file(root,rec); files[rec['file']]=rec['sha256']; return p
        except Exception as e: errors.append(f'{kind}: {e}')
    if award!='EFFIE_GC_MAIN': errors.append('专项材料规则尚未完成独立核验'); return errors,files
    v=case.get('creative_video') or {}; p=file(v,'视频')
    if p:
        try:
            if p.suffix.lower()!='.mp4': raise ValueError('仅支持MP4预检')
            meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)],timeout=15))
            duration=float(meta['format']['duration']); vmax=kb.rule_value(award,'video_max_seconds'); vmb=kb.rule_value(award,'video_max_mb')
            if not math.isfinite(duration) or duration<=0 or not vmax or duration>vmax or not vmb or p.stat().st_size>vmb*1000000 or not any(s.get('codec_type')=='video' for s in meta['streams']): raise ValueError('视频实际时长/大小/轨道不符合规则')
        except Exception as e: errors.append(f'视频: {e}')
    prints=case.get('creative_print') or []; lo=kb.rule_value(award,'print_min_count'); hi=kb.rule_value(award,'print_max_count'); mb=kb.rule_value(award,'print_max_mb')
    if not isinstance(prints,list) or not isinstance(lo,int) or not isinstance(hi,int) or not lo<=len(prints)<=hi: errors.append('平面数量缺失或超限')
    for r in prints:
        p=file(r,'平面')
        if p:
            try:
                from PIL import Image
                with Image.open(p) as im:
                    if im.format not in {'JPEG','PNG'} or im.width*im.height>50_000_000: raise ValueError('图片格式/像素超出支持范围')
                    im.verify()
                if not mb or p.stat().st_size>mb*1000000: raise ValueError('图片大小超限')
            except Exception as e: errors.append(f'平面: {e}')
    auth=case.get('authorization') or {}
    for k in ('client_authorization_file','signed_agreement_file'):
        p=file(auth.get(k),k)
        if p:
            try:
                if p.suffix.lower()=='.pdf':
                    from pypdf import PdfReader
                    reader=PdfReader(p,strict=True)
                    if reader.is_encrypted or not reader.pages: raise ValueError('空白或加密 PDF')
                    for page in reader.pages: page.get_contents()
                elif p.suffix.lower()=='.docx':
                    from docx import Document
                    doc=Document(p)
                    if not doc.paragraphs and not doc.tables: raise ValueError('空 DOCX')
                else: raise ValueError('须提供 PDF/DOCX')
            except Exception as ex: errors.append(f'{k}: 授权文件解析失败: {ex}')
    return errors,files
