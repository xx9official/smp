import asyncio
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import discord
from aiohttp import web
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("astra-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
APPLICATION_CHANNEL_ID = int(os.getenv("APPLICATION_CHANNEL_ID", "0"))
INVITE_CHANNEL_ID = int(os.getenv("INVITE_CHANNEL_ID", "0"))
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))

WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.getenv("PORT", "10000"))  # 🔥 vigtigt til Render

STATE_FILE = "applications_state.json"
PUBLIC_SITE_ORIGIN = os.getenv("PUBLIC_SITE_ORIGIN", "*")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@dataclass
class Application:
    application_id: str
    minecraft_username: str
    discord_user_id: int
    age: str
    playstyle: str
    why_join: str
    experience: str
    extra: str = ""
    status: str = "pending"
    submitted_at: str = ""
    reviewed_by: Optional[int] = None
    message_id: Optional[int] = None


store = {}


def cors_headers():
    return {
        "Access-Control-Allow-Origin": PUBLIC_SITE_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }


def json_response(data, status=200):
    return web.Response(
        text=json.dumps(data),
        status=status,
        headers={"Content-Type": "application/json", **cors_headers()},
    )


def build_embed(app):
    embed = discord.Embed(
        title=f"Ny ansøgning • {app.minecraft_username}",
        color=0x7AA8FF,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(name="Minecraft", value=app.minecraft_username, inline=True)
    embed.add_field(name="Discord ID", value=str(app.discord_user_id), inline=True)
    embed.add_field(name="Alder", value=app.age, inline=True)
    embed.add_field(name="Spillestil", value=app.playstyle, inline=False)
    embed.add_field(name="Hvorfor Astra", value=app.why_join, inline=False)
    embed.add_field(name="Erfaring", value=app.experience, inline=False)

    if app.extra:
        embed.add_field(name="Ekstra", value=app.extra, inline=False)

    return embed


async def handle_apply(request):
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers())

    try:
        data = await request.json()
    except:
        return json_response({"error": "Invalid JSON"}, 400)

    required = ["minecraft_username", "discord_user_id", "age", "playstyle", "why_join", "experience"]
    if any(not data.get(f) for f in required):
        return json_response({"error": "Missing fields"}, 400)

    try:
        discord_id = int(data["discord_user_id"])
    except:
        return json_response({"error": "Invalid Discord ID"}, 400)

    app_data = Application(
        application_id=secrets.token_hex(6),
        minecraft_username=data["minecraft_username"],
        discord_user_id=discord_id,
        age=data["age"],
        playstyle=data["playstyle"],
        why_join=data["why_join"],
        experience=data["experience"],
        extra=data.get("extra", ""),
        submitted_at=datetime.now(timezone.utc).isoformat()
    )

    channel = bot.get_channel(APPLICATION_CHANNEL_ID)
    if not channel:
        return json_response({"error": "Channel not found"}, 500)

    embed = build_embed(app_data)
    await channel.send(embed=embed)

    return json_response({"ok": True})


async def start_web():
    app = web.Application()
    app.router.add_route("POST", "/api/apply", handle_apply)
    app.router.add_route("OPTIONS", "/api/apply", handle_apply)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()

    logger.info(f"API kører på port {WEB_PORT}")


@bot.event
async def on_ready():
    logger.info(f"Bot online som {bot.user}")


async def main():
    async with bot:
        await start_web()

        while True:
            try:
                await bot.start(DISCORD_TOKEN)
            except Exception as e:
                logger.error(f"Bot crashed: {e}")
                logger.info("Retry om 10 sek...")
                await asyncio.sleep(10)


asyncio.run(main())
