"""Historical supervisor checkpoints never authorize execution/recovery."""
from .model import CheckpointSnapshot


def _run(*args, **kwargs):
    raise RuntimeError('retired: global checkpoint recovery is not executable')


def inspect_checkpoint(repo_root, state_file):
    return CheckpointSnapshot(False,False,False,None,None,False,None,False,False,True)


def active_lane_allows(*args, **kwargs):
    return False, 'retired: C3 owns scheduling and per-run recovery'
