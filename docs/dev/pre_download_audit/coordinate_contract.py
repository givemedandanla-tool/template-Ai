"""Resolve the precise object/index highlighted by original UTF-16 ranges."""
import ast

def index_for_diagnostic(tree,lines,position,rule):
    begin=tuple(position['start'][k] for k in ['line','character'])
    end=tuple(position['end'][k] for k in ['line','character'])
    def coordinate(node,which):
        line=getattr(node,'lineno' if which=='start' else 'end_lineno')
        col=getattr(node,'col_offset' if which=='start' else 'end_col_offset')
        return line-1,len(lines[line-1].encode()[:col].decode().encode('utf-16-le'))//2
    def exact(node):return coordinate(node,'start')==begin and coordinate(node,'end')==end
    subs=[n for n in ast.walk(tree) if isinstance(n,ast.Subscript)]
    candidates=([n for n in subs if exact(n.value)] if rule in ['reportOptionalSubscript','reportIndexIssue']
                else [n for n in subs if exact(n) or exact(n.slice)])
    return candidates[0] if len(candidates)==1 else None
