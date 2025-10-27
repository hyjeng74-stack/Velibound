class EventBus:
    def __init__(self):
        self._subs = {}
    def on(self, name, fn):
        self._subs.setdefault(name, []).append(fn)
    def emit(self, name, **kw):
        for fn in self._subs.get(name, []):
            fn(**kw)