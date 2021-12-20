class Model:

    def __init__(self, data):
        self._data = data

    def normalize(self, dest=None):
        raise NotImplementedError()

    def fit(self):
        pass