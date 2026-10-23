"""Publication view: omit local worker lease identifiers; never transform live job state."""
def public_audit(value):
    if isinstance(value,list):return [public_audit(v) for v in value]
    if isinstance(value,dict):
        result={k:public_audit(v) for k,v in value.items() if k!='token'}
        if 'token' in value:result['local_lease_identifier_omitted']=True
        return result
    return value
