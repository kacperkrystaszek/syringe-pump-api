import virtualserialports


class Loopback(object):
    def __init__(self):
        virtualserialports.run(1, True)