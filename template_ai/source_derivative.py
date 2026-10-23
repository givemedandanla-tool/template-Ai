"""Deterministic identities for hash-pinned derivative SVG channels."""
QUERY_IDS_VERSION='ta-query-1'


def assign_query_ids(root):
    elements=list(root.iter())
    existing=[node.get('id') for node in elements if node.get('id')]
    if len(existing)!=len(set(existing)):
        raise ValueError('SVG ID 不唯一，不能唯一映射')
    names=set(existing)
    for index,node in enumerate(elements):
        if not node.get('id'):
            key='ta-query-'+str(index)
            while key in names:key+='-'
            node.set('id',key);names.add(key)
    return elements
