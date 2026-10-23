"""Admit only precise, successful expression witnesses; retain all type debt.

Executed types demonstrate a bounded path, not correctness for arbitrary inputs.
Operator/iterable coordinates must identify the original offending operation;
normal calls alone do not waive incompatible argument or callback contracts.
"""
import argparse,ast,collections,json,re
from pathlib import Path
F=Path(__file__).resolve().parent;ORIGINAL=Path('/tmp/template-ai-audit-original-373b6ee')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);parser.add_argument('--kind',choices=['tests','capture'],default='tests');parser.add_argument('--points',type=Path,default=F/'runtime-points-006.json');args=parser.parse_args()
run=F/args.run;observation=json.loads((run/'observations.json').read_text());source=json.loads((run/'source.json').read_text())
assert observation['statuses']=={'PASS':observation['selected']} and not observation['runtime_errors'] and not observation['observer_errors'] and observation['source_unchanged'] and observation['business_ast_equivalence_verified']
points={p['id']:p for p in json.loads(args.points.read_text())['points']};results={r['id']:r['status'] for r in json.loads((run/('tests.json' if args.kind=='tests' else 'capture-contexts.json')).read_text())}
ROOT=F.parents[2]
class_locations=collections.defaultdict(set)
for file in (ROOT/'template_ai').glob('*.py'):
    tree=ast.parse(file.read_text());module='template_ai.'+file.stem
    for definition in tree.body:
        if isinstance(definition,ast.ClassDef):class_locations[definition.name].add(module+'.'+definition.name)
ledger=F/'diagnostic-ledger.jsonl';rows=[json.loads(x) for x in ledger.read_text().splitlines()];module_contexts=json.loads((run/'module-contexts.json').read_text()) if (run/'module-contexts.json').exists() else {}
proof_file=F/'exact-ast-contract-proof.json';proof=json.loads(proof_file.read_text()).get('proof',{}) if proof_file.exists() else {};counts=collections.Counter();line_cache={}

def exact_original(row,point,label):
    path=row['original']['path']
    if path not in line_cache:line_cache[path]=(ORIGINAL/path).read_text().splitlines()
    lines=line_cache[path];r=row['original_range'];wanted=[r['start']['line'],r['start']['character'],r['end']['line'],r['end']['character']]
    for target in point['targets']:
        if target['label']!=label or 'original_expression_range' not in target:continue
        a,b,c,d=target['original_expression_range'];actual=[a-1,len(lines[a-1].encode()[:b].decode().encode('utf-16-le'))//2,c-1,len(lines[c-1].encode()[:d].decode().encode('utf-16-le'))//2]
        if actual==wanted:return True
    return False

def exact_call_binding(row,point,keyword=False):
    path=row['original']['path'];text=(ORIGINAL/path).read_text();lines=text.splitlines();tree=ast.parse(text)
    r=row['original_range'];target=(r['start']['line'],r['start']['character'],r['end']['line'],r['end']['character'])
    def coordinates(n):
        return (n.lineno-1,len(lines[n.lineno-1].encode()[:n.col_offset].decode().encode('utf-16-le'))//2,n.end_lineno-1,len(lines[n.end_lineno-1].encode()[:n.end_col_offset].decode().encode('utf-16-le'))//2)
    selected=[t.get('original_expression_range') for t in point['targets'] if t['label']=='call_result']
    if len(selected)!=1:return False
    candidates=[]
    for call in ast.walk(tree):
        if not isinstance(call,ast.Call):continue
        match=(any(k.arg is None and coordinates(k.value)==target for k in call.keywords) if keyword else coordinates(call)==target or coordinates(call.func)==target)
        if match:candidates.append([call.lineno,call.col_offset,call.end_lineno,call.end_col_offset])
    return len(candidates)==1 and selected[0]==candidates[0]

def compatible_argument(expected,types):
    parts=[];depth=0;start=0
    for i,c in enumerate(expected):
        if c in '[(':depth+=1
        elif c in '])':depth-=1
        elif c=='|' and depth==0:parts.append(expected[start:i].strip());start=i+1
    if parts:
        parts.append(expected[start:].strip())
        return all(any(compatible_argument(part,{t}) for part in parts) for t in types)
    if expected in ['None','NoneType']:return types=={'builtins.NoneType'}
    if expected in ['StrPath','StrOrBytesPath']:
        return types<={'builtins.str','pathlib.PosixPath','pathlib.WindowsPath'}|({'builtins.bytes'} if expected=='StrOrBytesPath' else set())
    if expected in ['dict[Unknown, Unknown]','dict'] and types=={'builtins.dict'}:return True
    if any(expected.startswith(x) for x in ['SupportsRSub[','SupportsDunderLT[','SupportsDunderLE[','SupportsAbs[','SupportsRound[']):
        return types<={'builtins.int','builtins.float','numpy.float64','numpy.int64'}
    if expected=='ModuleSpec':return types=={'_frozen_importlib.ModuleSpec'}
    if expected=='PathLike[bytes]':return False
    if expected in ['Path','PathLike[str]','PathLike','PurePath']:
        allowed={'pathlib.PosixPath','pathlib.WindowsPath'}
        if expected!='Path':allowed|={'pathlib.PurePosixPath','pathlib.PureWindowsPath'}
        return types<=allowed
    if re.fullmatch(r'[A-Z][A-Za-z0-9_]*',expected):
        locations=class_locations.get(expected,set())
        if len(locations)==1 and types<=locations:return True
        if expected.startswith('Q') and all(t.startswith('PySide6.') and t.rsplit('.',1)[-1]==expected for t in types):return True
    primitives={'str':{'builtins.str'},'int':{'builtins.int'},'float':{'builtins.int','builtins.float','numpy.float64'},'bool':{'builtins.bool'},'bytes':{'builtins.bytes'}}
    if expected in primitives:return types<=primitives[expected]
    if re.fullmatch(r'Iterable\[(?:_T(?:@[A-Za-z_]+)?|Unknown)\]',expected):
        return types<={'builtins.str','builtins.bytes','builtins.list','builtins.dict','builtins.tuple','builtins.set','builtins.frozenset','builtins.range','builtins.dict_keys','builtins.dict_values','builtins.dict_items','builtins.generator'}
    if expected=='Sized':return types<={'builtins.str','builtins.bytes','builtins.list','builtins.dict','builtins.tuple','builtins.set','builtins.frozenset','builtins.range'}
    if expected in ['_SupportsFloatOrIndex','SupportsFloat','SupportsIndex']:
        return types<=({'builtins.int'} if expected=='SupportsIndex' else {'builtins.int','builtins.float'})
    return False

for row in rows:
    if row['status']!='UNREVIEWED' or row['id'] not in observation['rows']:continue
    key=row['id'];actual=observation['rows'][key];point=points[key];contexts=[t for t in actual['test_contexts'] if results.get(t)=='PASS']
    if not contexts:
        contexts=['owned-module:'+m for m in actual.get('module_contexts',[]) if m in module_contexts and module_contexts[m]['receipt']['healthy'] and all(results.get(t)=='PASS' for t in module_contexts[m]['tests'])]
    if not contexts:continue
    values=actual['values'];types={label:set(v) for label,v in values.items()};rule=row['rule'];message=row['original']['message'];kind=None;reason=None
    containers=types.get('container',set());receivers=types.get('receiver',set())
    if rule in ['reportOptionalSubscript','reportIndexIssue'] and containers and containers<={'builtins.dict','builtins.list','builtins.tuple','builtins.str','builtins.bytes'}:
        kind='EXACT_EXECUTED_CONTAINER';reason='The exact indexed receiver is a concrete builtin container on the listed executed paths. No claim that arbitrary keys or indices exist.'
    elif rule in ['reportArgumentType','reportCallIssue'] and any(op in message for op in ['__getitem__','__setitem__']) and containers=={'builtins.dict'}:
        kind='EXACT_EXECUTED_DICT_KEY_CONTRACT';reason='The exact indexed object is a dict, not a list/string/int member of the inferred heterogeneous union. Keep independent key/ownership validation.'
    elif rule in ['reportArgumentType','reportCallIssue'] and '__getitem__' in message and containers and containers<={'builtins.list','builtins.tuple'} and types.get('result'):
        from coordinate_contract import index_for_diagnostic
        original_text=(ORIGINAL/row['original']['path']).read_text()
        indexed=index_for_diagnostic(ast.parse(original_text),original_text.splitlines(),row['original_range'],rule)
        if indexed is not None and isinstance(indexed.slice,ast.Constant) and type(indexed.slice.value) is int:
            kind='EXACT_COMPLETED_CONSTANT_SEQUENCE_INDEX';reason='The precisely selected indexed receiver is a builtin list/tuple, its original key is a literal integer, and the original indexing operation completed with a recorded result. Static record-union inference instead selects a string-key mapping/slice overload. This does not guarantee arbitrary indices or future list lengths.'
    elif rule in ['reportAttributeAccessIssue','reportOptionalMemberAccess'] and not message.startswith('Cannot assign') and receivers and 'builtins.NoneType' not in receivers and types.get('member_value'):
        kind='EXACT_EXECUTED_MEMBER';reason='Original attribute evaluation succeeded on its actual receiver, including dynamic factories/proxies. Getter is evaluated once; this does not guarantee a nullable member value is non-null.'
    elif rule in ['reportGeneralTypeIssues','reportOptionalIterable'] and exact_original(row,point,'iterable') and types.get('iterable') and types['iterable']<={'builtins.list','builtins.tuple','builtins.dict','builtins.str','builtins.bytes','builtins.set','builtins.frozenset','builtins.range','builtins.dict_keys','builtins.dict_values','builtins.dict_items','builtins.generator'}:
        kind='EXACT_EXECUTED_ITERABLE';reason='The exact original iterator expression has a builtin iterable type on observed paths; unrelated revision/status scalar fields must not be merged with this named field.'
    elif rule in ['reportOperatorIssue','reportOptionalOperand'] and types.get('operation') and 'builtins.NoneType' not in types['operation'] and any(exact_original(row,point,label) for label in ['operation','operator_left','operator_right']):
        kind='EXACT_COMPLETED_OPERATOR';reason='The precisely highlighted operation completed normally with the recorded operand/result types. Original assertions and independent numeric oracles remain separate; no arbitrary-input or model-quality claim.'
    elif rule=='reportArgumentType' and types.get('argument') and types.get('call_result'):
        match=re.search(r'to parameter "([^"]+)" of type "([^"]+)"',message)
        function=re.search(r'in function "([^"]+)"',message)
        calls=[t for t in point['targets'] if t['label']=='call_result']
        if match and function and len(calls)==1:
            call=ast.parse(calls[0]['expression'],mode='eval').body
            name=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else None
            same=(name==function[1] or function[1] in ['__init__','__new__'] and name and (name[0].isupper() or name in ['str','int','float','dict','list','set','tuple','bytes','bool']))
            if same and function[1] in ['__init__','__new__'] and name in ['QTableWidgetItem','QLineEdit','QLabel'] and types['argument']=={'builtins.str'} and all(t.startswith('PySide6.') and t.rsplit('.',1)[-1]==name for t in types['call_result']):
                kind='EXACT_QT_STRING_CONSTRUCTOR_OVERLOAD';reason='The exact argument is str and the actual Qt string constructor completed with its expected widget/item type. The diagnostic selects the int/parent overload from an untyped union. None/other constructor arguments are not waived.'
            elif same and name=='dict' and types['argument']=={'builtins.dict'} and types['call_result']=={'builtins.dict'} and match[2].startswith('Iterable[tuple['):
                kind='EXACT_MAPPING_CONSTRUCTOR_OVERLOAD';reason='The exact dict constructor received a builtin mapping and completed as dict, matching its Mapping overload. The inferred homogeneous kwargs value type selects a narrower Iterable-of-tuples signature. Heterogeneous named-field schema remains DTO debt; no arbitrary payload content or output qualification is approved.'
            elif same and compatible_argument(match[2],types['argument']):
                kind='EXACT_COMPATIBLE_ARGUMENT_AND_RETURN';reason=f'Parameter {match[1]} expects {match[2]}; its exact observed argument type is compatible and the actual selected call returned normally. Other union members/preconditions remain guarded; callback/generic-content mismatches are not waived.'
    if kind is None and types.get('call_result'):
        if rule=='reportCallIssue' and (message.startswith('Arguments missing for parameters') or 'not callable' in message or re.match(r'Expected [0-9]+ positional argument',message)) and exact_call_binding(row,point):
            kind='EXACT_CALL_ARITY_OR_CALLABILITY';reason='The precisely selected call returned normally, so its actual callable and required argument binding succeeded on these paths. This does not prove all payload contents or callback arities connected for future execution.'
        elif rule=='reportCallIssue' and message.startswith('No overloads for ') and exact_call_binding(row,point):
            kind='EXACT_COMPLETED_OVERLOAD_BINDING';reason='The precisely selected original call completed, proving its actual callable accepted this argument binding on the retained authored paths. Static overload resolution over inferred unions/protocols is incomplete. Semantic output, generic contents and unseen arguments are not approved by this binding witness.'
        elif rule=='reportArgumentType' and message.startswith('Argument expression after ** must be a mapping with a "str" key type') and exact_call_binding(row,point,keyword=True):
            kind='EXACT_COMPLETED_KEYWORD_MAPPING';reason='CPython completed the exact **kwargs call, which requires a mapping with string keyword keys. Named-field numeric/ownership/shape validation remains separate; the source DTO is insufficiently described.'
    if kind is None and row['scope'] in ['tests','tools'] and rule=='reportArgumentType' and types.get('call_result') and re.search(r'to parameter "self" of type "[A-Za-z_][A-Za-z0-9_]*Tests"',message):
        calls=[t for t in point['targets'] if t['label']=='call_result']
        if len(calls)==1:
            call=ast.parse(calls[0]['expression'],mode='eval').body
            if isinstance(call.func,ast.Attribute) and (call.func.attr in ['setUp','tearDown'] or re.search(r'in function "'+re.escape(call.func.attr)+r'"',message)):
                kind='EXACT_SHARED_FIXTURE_HOST_CONTRACT';reason='The authored test/capture deliberately delegates fixture setup/cleanup across TestCase hosts. The real original method returned normally, constructing/disposing its real resources. Its class-specific fixture-helper self annotation is narrower than the reused fixture interface; this does not substitute a product window.'
    if not kind:continue
    proof[key]=dict(kind=kind,reason=reason,original=row['original'],original_range=row['original_range'],point=point,observed_types=values,member_checks=actual['member_checks'],passing_contexts=contexts,context_granularity='MODULE_ONLY' if contexts[0].startswith('owned-module:') else 'EXACT_CASE_OR_CAPTURE',execution_kind=args.kind,source=run.relative_to(F).as_posix()+'/source.json',observations=run.relative_to(F).as_posix()+'/observations.json',bounds='Only retained authored samples, max128 observations per point; no private corpus/Windows/physical print/arbitrary input qualification',followup='Precise producer DTO/host/callable typing remains P2; do not use Any, ignore rules, or refresh baseline.')
    row.update(status='TYPE_CONTRACT_GAP',severity='P2_EXACT_EXPRESSION_CONTRACT_DEBT',affected_workflow=row['original']['path'],root_cause_or_blocker=reason,evidence=['exact-ast-contract-proof.json#'+key],repro_command_and_result='Original unchanged source/Qt/assertions, transparent instrumented bytecode; business AST is identical after unwrapping; exact scope/test/source hashes in proof',regression_and_result=contexts,remaining_condition='Type descriptions still need improvement; preserve all runtime validation and deferred qualification boundaries.')
    counts[kind]+=1
ledger.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));proof_file.write_text(json.dumps(dict(method=__doc__,proof=proof,counts=dict(collections.Counter(p['kind'] for p in proof.values()))),ensure_ascii=False,indent=2)+'\n');print(dict(counts))
