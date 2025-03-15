import asyncio
import json
import aiohttp
import websockets
import uuid

CHECKIN_URL = "https://director.getgrass.io/checkin"
RECONNECT_INTERVAL = 5  # seconds
PING_INTERVAL = 60  # seconds
HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg",
    "priority": "u=1, i",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "none",
    "sec-fetch-storage-access": "active",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}
ws_headers = {
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg",
    "Pragma": "no-cache",
    "Sec-Websocket-Extensions": "permessage-deflate; client_max_window_bits",
    "Sec-Websocket-Key": "6M+h35F59kz8IDzq41KEnw==",
    "Sec-WebSocket-Version": "13",
    "Upgrade": "websocket",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}


async def get_local_storage():
    # Simulating getting local storage data (you may need to replace this with actual storage retrieval)
    return {
        "browserId": "your_browser_id",
        "userId": "your_user_id",
        "permissions": True,
    }

async def checkin():
    # storage = await get_local_storage()
    
    # if not storage.get("browserId") or not storage.get("permissions") or not storage.get("userId"):
    #     print("[CHECKIN] Missing required parameters: BROWSER ID, PERMISSIONS, or USER ID")
    #     return None
    
    payload = {
        "browserId": "6335bf8b-7294-5d8e-8bbc-75cb2b0fdfe3",
        "userId": "e5ace647-0cb8-46f8-9d47-19abd6d72b1c",
        "version": "5.1.1",
        "extensionId": "ilehaonighjijnmpnagapkhpcdbhclfg",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "deviceType": "extension"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(CHECKIN_URL, json=payload, headers=HEADERS) as response:
            text_response = await response.text()  # Read response as text
            
            if response.status == 201:
                try:
                    data = json.loads(text_response)  # Manually parse JSON
                    return data
                except json.JSONDecodeError:
                    print(f"[CHECKIN] Failed to decode JSON: {text_response}")
                    return None
            else:
                print(f"[CHECKIN] Failed with status {response.status}: {text_response}")
                return None

async def websocket_handler(destination, token):
    retries = 0
    max_retries = 5
    
    while retries < max_retries:
        try:
            async with websockets.connect(f"ws://{destination}?token={token}") as ws:
                print("[WEBSOCKET] Connected")

                async def send_ping():
                    while True:
                        ping_message = json.dumps({
                            "id": str(uuid.uuid4()),
                            "version": "1.0.0",
                            "action": "PING",
                            "data": {}
                        })
                        await ws.send(ping_message)
                        print(f"[WEBSOCKET] Sent: {ping_message}")
                        await asyncio.sleep(PING_INTERVAL)

                async def receive_messages():
                    while True:
                        try:
                            message = await ws.recv()
                            try:
                                parsed_message = json.loads(message)
                                print(f"[WEBSOCKET] Received: {parsed_message}")
                            except json.JSONDecodeError:
                                print("[WEBSOCKET] Could not parse message!", message)
                        except websockets.exceptions.ConnectionClosed:
                            print("[WEBSOCKET] Connection closed by server. Reconnecting...")
                            return

                # Run send and receive tasks concurrently
                await asyncio.gather(send_ping(), receive_messages())

        except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError) as e:
            print(f"[WEBSOCKET] Connection error: {e}. Retrying in {RECONNECT_INTERVAL} seconds...")
            await asyncio.sleep(RECONNECT_INTERVAL)
            retries += 1

    print("[WEBSOCKET] Maximum retries reached. Connection failed.")

async def main():
    data = await checkin()
    if not data:
        return
    
    destinations = data.get("destinations", [])
    token = data.get("token")
    
    if not destinations or not token:
        print("[ERROR] No destinations or token found!")
        return
    
    await websocket_handler(destinations[0], token)  # Connect to the first destination

asyncio.run(main())
