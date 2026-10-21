"""Report interpreter mode only in authored GitHub release acceptance runs."""
import os
import sys

if os.environ.get('GITHUB_ACTIONS')=='true':
    print('FROZEN_UTF8_MODE='+str(sys.flags.utf8_mode),file=sys.stderr,flush=True)
