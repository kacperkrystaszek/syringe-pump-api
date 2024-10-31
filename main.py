from server import Server

if __name__ == "__main__":
    server = Server()
    try:
        server.run()
    except Exception as exc:
        print(exc)
        for process in server.loopback.values():
            process.kill()
        server.close()