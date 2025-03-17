import asyncio
import json
import aiohttp
import websockets
import uuid
from rich.console import Console
from rich.text import Text
import os

console = Console()

CHECKIN_URL = "https://director.getgrass.io/checkin"
USER_INFO_URL = "https://api.getgrass.io/retrieveUser"
CHECKIN_INTERVAL = 137
WEBSOCKET_DURATION = 137
PING_INTERVAL = 60  # 1 minute

HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

async def handle_http_request(data):
    """Handles HTTP_REQUEST and ensures the response matches the expected format."""
    url = data.get("url")
    method = data.get("method", "GET")
    headers = data.get("headers", {})
    body = data.get("body", None)

    print(f"[RPC] Processing HTTP_REQUEST: {data}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method, url, headers=headers, data=body) as resp:
                response_data = await resp.text()
                formatted_response = {
                    "url": url,
                    "status": resp.status,
                    "status_text": resp.reason,
                    "headers": dict(resp.headers),
                    "body": response_data
                }
                print(f"[RPC] HTTP_REQUEST Result: {formatted_response}")
                return formatted_response

        except Exception as e:
            print(f"[RPC] HTTP_REQUEST failed: {e}")
            return {"error": str(e)}

RPC_CALL_TABLE = {
    "HTTP_REQUEST": handle_http_request
}

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def user_token():
    try:
        with open("user_token.txt", "r") as file:
            return file.readline().strip()
    except FileNotFoundError:
        console.print("[red][ERROR][/red] user_token.txt not found.")
        return None
    except Exception as e:
        console.print(f"[red][ERROR][/red] Unexpected error: {e}")
        return None

async def retrieve_user_info():
    headers = HEADERS.copy()
    token = user_token()
    
    if not token:
        console.print("[red][ERROR][/red] No user token found, exiting.")
        return None

    headers["Authorization"] = f"{token}"

    async with aiohttp.ClientSession() as session:
        try:
            console.print("[blue][INFO][/blue] Fetching user info...")
            async with session.get(USER_INFO_URL, headers=headers) as response:
                text_response = await response.text()

                if response.status == 200:
                    try:
                        data = json.loads(text_response)
                        return data.get("result", {}).get("data", None)
                    except json.JSONDecodeError:
                        console.print(f"[red][ERROR][/red] Failed to parse user info JSON: {text_response}")
                else:
                    console.print(f"[red][ERROR][/red] User info request failed (Status {response.status}): {text_response}")

        except Exception as e:
            console.print(f"[red][ERROR][/red] Request to retrieve user info failed: {e}")

    return None

async def websocket_handler(destination, token):
    """ Handles WebSocket communication and automatic reconnects. """
    ws_url = f"ws://{destination}?token={token}"
    console.print(f"[green][WEBSOCKET][/green] Connecting to: [blue]{destination}[/blue] websocket...")

    try:
        async with websockets.connect(ws_url) as ws:
            console.print(f"[green][WEBSOCKET][/green] Connected!")

            async def send_ping():
                while True:
                    ping_message = json.dumps({
                        "id": str(uuid.uuid4()),
                        "version": "1.0.0",
                        "action": "PING",
                        "data": {}
                    })
                    await ws.send(ping_message)
                    console.print(f"[green][WEBSOCKET][/green] Sent: [blue]{ping_message}[/blue]")
                    await asyncio.sleep(PING_INTERVAL)

            async def receive_messages():
                while not ws.closed:
                    try:
                        message = await ws.recv()
                        parsed_message = json.loads(message)
                        console.print(f"[green][WEBSOCKET][/green] Received: [blue]{parsed_message}[/blue]")

                        if parsed_message.get("action") in RPC_CALL_TABLE:
                            console.print(f"[green][WEBSOCKET][/green] Inside of: [blue]RPC_CALL_TABLE[/blue]")
                            try:
                                result = await RPC_CALL_TABLE[parsed_message["action"]](parsed_message.get("data", {}))
                                response = {
                                    "id": parsed_message.get("id", str(uuid.uuid4())),
                                    "origin_action": parsed_message["action"],
                                    "result": result
                                }
                                await ws.send(json.dumps(response))
                                print(f"[WEBSOCKET] Sent response: {response}")

                            except Exception as e:
                                print(f"[WEBSOCKET] RPC error: {e}")
                        elif parsed_message.get("action") == "PONG":
                            response = {
                                "id": parsed_message.get("id"),
                                "origin_action": "PONG"
                            }
                            await ws.send(json.dumps(response))
                            print(f"[WEBSOCKET] Auto-responded to PONG: {response}")
                        else:
                            print(f"[WEBSOCKET] Unhandled WebSocket action: {parsed_message.get('action')}")
                    except websockets.exceptions.ConnectionClosed:
                        console.print(f"[red][WEBSOCKET][/red] Connection lost. Reconnecting...")
                        return
                    except json.JSONDecodeError:
                        console.print(f"[red][WEBSOCKET][/red] Invalid JSON received: {message}")

            task1 = asyncio.create_task(send_ping())
            task2 = asyncio.create_task(receive_messages())

            await asyncio.sleep(WEBSOCKET_DURATION)
            print("[WEBSOCKET] 137 seconds passed, closing WebSocket...")

            task1.cancel()
            task2.cancel()
            await ws.close()
            
    except Exception as e:
        console.print(f"[red][WEBSOCKET][/red] Connection failed: {e}. Retrying in 5 seconds...")
    await checkin()

async def checkin():
    payload = {
        "browserId": "6335bf8b-7294-5d8e-8bbc-75cb2b0fdfe3",
        "userId": "e5ace647-0cb8-46f8-9d47-19abd6d72b1c",
        "version": "5.1.1",
        "extensionId": "ilehaonighjijnmpnagapkhpcdbhclfg",
        "userAgent": HEADERS["User-Agent"],
        "deviceType": "extension"
    }

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                console.print(f"[blue][INFO][/blue] Sending check-in request to: [green]{CHECKIN_URL}[/green]...")

                async with session.post(CHECKIN_URL, json=payload, headers=HEADERS) as response:
                    text_response = await response.text()

                    if response.status == 201:
                        data = json.loads(text_response)
                        destinations = data.get("destinations", [])
                        token = data.get("token")

                        if destinations and token:
                            console.print(f"[green][CHECKIN][/green] Found WebSocket destination: {destinations[0]}")
                            await websocket_handler(destinations[0], token)
                        else:
                            console.print("[red][CHECKIN][/red] No WebSocket destination received.")

                    else:
                        console.print(f"[red][CHECKIN][/red] Check-in failed with status {response.status}: {text_response}")

            except Exception as e:
                console.print(f"[red][CHECKIN][/red] Error: {e}")

            console.print(f"[blue][INFO][/blue] Next check-in in [green]{CHECKIN_INTERVAL}[/green] seconds...")
            await asyncio.sleep(CHECKIN_INTERVAL)

if __name__ == "__main__":
    console.print("[blue][STARTING][/blue] Running bot...")
    asyncio.run(checkin())
