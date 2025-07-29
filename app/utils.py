clients = set()

async def broadcast(message):
    disconnected = set()
    for ws in clients:
        try:
            await ws.send_json(message)
        except:
            disconnected.add(ws)
    clients.difference_update(disconnected)
