class Event(object):
    callbacks = {}

    @classmethod
    def register(self, eventname, callback):
        if not self.callbacks.has_key(eventname):
            self.callbacks[eventname] = []
        self.callbacks[eventname].append(callback)



    @classmethod
    def trigger(self, eventname, *args, **kwargs):
        if not self.callbacks.has_key(eventname):
            return 
        for c in self.callbacks[eventname]:
            c(*args, **kwargs)
