"""Read public GitHub Git objects; retain raw responses and verify tree hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

CACHE = None

API = 'https://api.github.com/repos/givemedandanla-tool/template-Ai/git/'

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def fetch(url, path):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    if CACHE and path.parent.name == 'raw-trees' and (CACHE/path.name).exists():
        raw = (CACHE/path.name).read_bytes()
        path.write_bytes(raw)
        return json.loads(raw)
    req = urllib.request.Request(url, headers={'User-Agent': 'template-Ai-verified-readback', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
    value = json.loads(raw)
    path.write_bytes(raw)
    return value

def main():
    global CACHE
    parser=argparse.ArgumentParser()
    parser.add_argument('commit')
    parser.add_argument('output', type=Path)
    parser.add_argument('--cache', type=Path)
    args=parser.parse_args()
    CACHE = args.cache
    folder=args.output;folder.mkdir(parents=True,exist_ok=True)
    commit=fetch(API+'commits/'+args.commit,folder/'commit.json')
    if commit['sha'] != args.commit:
        raise ValueError('Unexpected commit')
    rawdir=folder/'raw-trees';rawdir.mkdir(exist_ok=True)
    def walk(sha, prefix=''):
        if prefix not in ('', 'docs', 'docs/dev'):
            tree=fetch(API+'trees/'+sha+'?recursive=1',rawdir/(sha+'.recursive.json'))
            if tree['sha'] != sha: raise ValueError('Wrong tree SHA')
            if not tree.get('truncated'):
                return tree['tree']
        direct=fetch(API+'trees/'+sha,rawdir/(sha+'.direct.json'))
        if direct.get('truncated'):raise ValueError('Direct tree truncated')
        result=list(direct['tree'])
        for item in direct['tree']:
            if item['type']=='tree':
                for child in walk(item['sha'],prefix+'/'+item['path'] if prefix else item['path']):
                    result.append(dict(child,path=item['path']+'/'+child['path']))
        return result
    entries=walk(commit['tree']['sha'])
    paths={e['path']:e for e in entries}
    if len(paths)!=len(entries):raise ValueError('Duplicate paths')
    children={}
    for path,item in paths.items():
        parent,_,name=path.rpartition('/')
        children.setdefault(parent,[]).append((name,item))
    for directory,items in children.items():
        payload=b''
        for name,item in sorted(items,key=lambda pair:(pair[0]+('/' if pair[1]['type']=='tree' else '')).encode('utf-8')):
            payload+=(item['mode'].lstrip('0')+' '+name).encode('utf-8')+b'\0'+bytes.fromhex(item['sha'])
        actual=hashlib.sha1(b'tree '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
        expected=paths[directory]['sha'] if directory else commit['tree']['sha']
        if actual!=expected:raise ValueError('Tree hash mismatch: '+directory)
    tree={'sha':commit['tree']['sha'],'url':API+'trees/'+commit['tree']['sha'],'tree':entries,'truncated':False,
          'verification':'Complete recursive tree assembled from retained raw GitHub API responses; every directory Git tree SHA recomputed.'}
    save(folder/'tree.json',tree)
    save(folder/'readback-summary.json',{'commit':commit['sha'],'tree':tree['sha'],'entries':len(entries),'verified_directory_hashes':len(children),'raw_responses':len(list(rawdir.glob('*.json'))),'truncated':False})
    print(json.dumps({'commit':commit['sha'],'tree':tree['sha'],'entries':len(entries),'verified_directory_hashes':len(children),'raw_responses':len(list(rawdir.glob('*.json'))),'truncated':False}),flush=True)

if __name__=='__main__':main()
