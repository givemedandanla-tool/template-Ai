"""Optional backend admission hook at durable unit boundaries; never marks a unit failed."""
class ResourcePause(Exception):
    pass


def require_resources(admission):
    if admission:
        decision=admission()
        if not decision.allowed:raise ResourcePause(','.join(decision.reasons))
