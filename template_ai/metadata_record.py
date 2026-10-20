"""Decode the complete training metadata row selected by one SQLite statement."""
import json


def training_record(row):
    identity, revision, payload = row
    return {'id': identity, 'revision': revision, **json.loads(payload)}
