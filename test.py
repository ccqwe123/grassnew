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
CHECKIN_INTERVAL = 300  # 5 minutes
PING_INTERVAL = 60  # 1 minute

HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def user_token():
    try:
        with open("user_token.txt", "r") as file:
            return file.readline().strip()
    except FileNotFoundError:
        print("[ERROR] user_token.txt not found.")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return None
    
def print_header(username, total_points, total_uptime):
    text = " SPLEKENESIS BOT"
    border = "*" * (len(text) + 30)
    console.print(f"[green]{border}[/green]")
    console.print(f"[green][red]{text}[/red] [blue]v2.5[/blue]              [/green]")
    console.print(f"[green] [white]Username: [/white][red]{username}[/red]               [/green]")
    console.print(f"[green] [white]Total UpTime: [/white][red]{total_uptime}[/red]               [/green]")
    console.print(f"[green] [white]Total Points: [/white][red]{total_points}[/red]               [/green]")
    console.print(f"[green]{border}[/green]")

async def retrieve_user_info():
    headers = HEADERS.copy()
    tokens = user_token()
    headers["Authorization"] = f"{tokens}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(USER_INFO_URL, headers=headers) as response:
                text_response = await response.text()

                if response.status == 200:
                    try:
                        data = json.loads(text_response)
                        user_info = data.get("result", {}).get("data", None)

                        if not user_info:
                            console.print(f"[red][ERROR][/red] User info missing in API response: {data}")
                        return user_info

                    except json.JSONDecodeError:
                        console.print(f"[red][ERROR][/red] Failed to parse user info JSON: {text_response}")

                else:
                    console.print(f"[red][ERROR][/red] Failed to fetch user info (Status {response.status}): {text_response}")

        except Exception as e:
            console.print(f"[red][ERROR][/red] Request to retrieve user info failed: {e}")

    return None  # Ensure we return None if there's an issue

async def websocket_handler(destination, token):
    """ Handles WebSocket communication and automatic reconnects. """
    ws_url = f"ws://{destination}?token={token}"
    
    while True:  # Keep retrying if the connection is lost
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
                    while True:
                        try:
                            message = await ws.recv()
                            try:
                                parsed_message = json.loads(message)
                                console.print(f"[green][WEBSOCKET][/green] Received: [blue]{parsed_message}[/blue]")
                            except json.JSONDecodeError:
                                console.print(f"[red][WEBSOCKET][/red] Could not parse message: {message}")
                        except websockets.exceptions.ConnectionClosed:
                            console.print(f"[red][WEBSOCKET][/red] Connection lost. Reconnecting...")
                            break  # Exit the receive loop to reconnect

                # Start WebSocket tasks
                ping_task = asyncio.create_task(send_ping())
                receive_task = asyncio.create_task(receive_messages())

                await asyncio.wait([ping_task, receive_task])

        except Exception as e:
            console.print(f"[red][WEBSOCKET][/red] Connection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)  # Retry after 5 seconds

async def checkin():
    """ Performs check-in and retrieves user info. """
    payload = {
        "browserId": "6335bf8b-7294-5d8e-8bbc-75cb2b0fdfe3",
        "userId": "e5ace647-0cb8-46f8-9d47-19abd6d72b1c",
        "version": "5.1.1",
        "extensionId": "ilehaonighjijnmpnagapkhpcdbhclfg",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "deviceType": "extension"
    }
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.post(CHECKIN_URL, json=payload, headers=HEADERS) as response:
                    text_response = await response.text()

                    if response.status == 201:
                        try:
                            user_info = await retrieve_user_info()
                            if user_info:
                                print_header(
                                    user_info.get('username', 'Unknown'),
                                    user_info.get('totalPoints', 0),
                                    user_info.get('totalUptime', 0)
                                )
                            else:
                                console.print(f"[red][CHECKIN][/red] Failed to retrieve user info")
                            
                            data = json.loads(text_response)
                            destinations = data.get("destinations", [])
                            token = data.get("token")

                            if not token:
                                console.print(f"[red][CHECKIN][/red] No token found.")
                                continue

                            if destinations:
                                console.print(f"[green][CHECKIN][/green] Connected to: [blue]{destinations[0]}[/blue]")
                                await websocket_handler(destinations[0], token)
                            else:
                                console.print(f"[red][CHECKIN][/red] No destinations found")

                        except json.JSONDecodeError:
                            console.print(f"[red][CHECKIN][/red] Failed to parse response: {text_response}")

                    else:
                        console.print(f"[red][CHECKIN][/red] Check-in failed: {response.status}")

            except Exception as e:
                console.print(f"[red][CHECKIN][/red] Error: {e}")

            console.print(f"[blue][INFO][/blue] Next check-in in [green]{CHECKIN_INTERVAL}[/green] seconds...")
            await asyncio.sleep(CHECKIN_INTERVAL)

# Start the bot
asyncio.run(checkin())
