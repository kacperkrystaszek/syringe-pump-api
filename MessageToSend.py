class MessageToSend:
    def __init__(self, command: str, time: int):
        self.command: str = command
        self.time: int = time

    def __repr__(self):
        return self.command
    