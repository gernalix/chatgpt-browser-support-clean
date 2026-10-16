"""Retired global supervisor; C3 owns bounded per-run executor recovery."""


class Supervisor:
    def __init__(self, *args, **kwargs):
        raise RuntimeError('retired: use a C3-managed on-demand executor')
