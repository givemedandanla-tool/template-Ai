"""Decode the complete training metadata row selected by one SQLite statement."""
import json


def logo_proposal_record(row):
    identity, revision, state, payload = row
    return dict(id=identity, revision=revision, state=state, **json.loads(payload))


def training_record(row):
    identity, revision, payload = row
    return {'id': identity, 'revision': revision, **json.loads(payload)}
