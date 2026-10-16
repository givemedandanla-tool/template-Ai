"""Explicit synthetic source-author review for positive format integration tests."""
def authored_review(candidate,format,folder,dpi=300):
    if format.upper()=='PNG':return None
    from template_ai.digital_output_proof import build_proof
    from template_ai.digital_review import confirm
    proof=build_proof(candidate,format,dpi,folder)
    return confirm(candidate,proof,'SYNTHETIC_SOURCE_AUTHOR',
        'Authored test source and actual same-format card snapshot checked before delivery',True)
