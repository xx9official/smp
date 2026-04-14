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
WEB_PORT = int(os.getenv("PORT", "10000"))
STATE_FILE = "applications_state.json"
PUBLIC_SITE_ORIGIN = os.getenv("PUBLIC_SITE_ORIGIN", "*")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN mangler.")

required_ids = {
    "GUILD_ID": GUILD_ID,
    "APPLICATION_CHANNEL_ID": APPLICATION_CHANNEL_ID,
    "INVITE_CHANNEL_ID": INVITE_CHANNEL_ID,
    "STAFF_ROLE_ID": STAFF_ROLE_ID,
}
missing_ids = [name for name, value in required_ids.items() if not value]
if missing_ids:
    raise RuntimeError(f"Disse værdier mangler: {', '.join(missing_ids)}")

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


class ApplicationStore:
    def __init__(self, path: str):
        self.path = path
        self.data: dict[str, dict] = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as file:
                self.data = json.load(file)
        else:
            self.data = {}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)

    def set(self, app: Application):
        self.data[app.application_id] = asdict(app)
        self.save()

    def get(self, application_id: str) -> Optional[Application]:
        raw = self.data.get(application_id)
        return Application(**raw) if raw else None

    def pending(self):
        return [Application(**raw) for raw in self.data.values() if raw.get("status") == "pending"]


store = ApplicationStore(STATE_FILE)


def cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": PUBLIC_SITE_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type, Accept",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }


def json_response(payload: dict, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        headers={"Content-Type": "application/json", **cors_headers()},
    )


def build_application_embed(
    application: Application,
    reviewed_by: Optional[discord.abc.User] = None,
    decision: Optional[str] = None,
) -> discord.Embed:
    color = 0x7AA8FF
    title_prefix = "Ny ansøgning"

    if decision == "Godkendt":
        color = 0x43B581
        title_prefix = "Godkendt ansøgning"
    elif decision == "Afvist":
        color = 0xF04747
        title_prefix = "Afvist ansøgning"

    embed = discord.Embed(
        title=f"{title_prefix} • {application.minecraft_username}",
        description="Whitelist-ansøgning fra hjemmesiden.",
        color=color,
        timestamp=datetime.fromisoformat(application.submitted_at) if application.submitted_at else discord.utils.utcnow(),
    )

    embed.add_field(name="Minecraft navn", value=application.minecraft_username, inline=True)
    embed.add_field(name="Discord user ID", value=str(application.discord_user_id), inline=True)
    embed.add_field(name="Alder", value=application.age, inline=True)
    embed.add_field(name="Spillestil", value=application.playstyle[:1024], inline=False)
    embed.add_field(name="Hvorfor Astra SMP?", value=application.why_join[:1024], inline=False)
    embed.add_field(name="Erfaring", value=application.experience[:1024], inline=False)

    if application.extra.strip():
        embed.add_field(name="Ekstra", value=application.extra[:1024], inline=False)

    embed.set_footer(
        text=f"Ansøgnings-ID: {application.application_id} • Status: {decision or application.status}"
    )

    if reviewed_by:
        embed.add_field(name="Behandlet af", value=reviewed_by.mention, inline=False)

    return embed


class DecisionView(discord.ui.View):
    def __init__(self, application_id: str):
        super().__init__(timeout=None)
        self.application_id = application_id

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        role_ids = [role.id for role in getattr(interaction.user, "roles", [])]
        if STAFF_ROLE_ID in role_ids:
            return True

        await interaction.response.send_message(
            "Du har ikke adgang til at behandle ansøgninger.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Godkend", style=discord.ButtonStyle.success, custom_id="astra:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return

        application = store.get(self.application_id)
        if not application:
            await interaction.response.send_message("Ansøgningen blev ikke fundet.", ephemeral=True)
            return

        if application.status != "pending":
            await interaction.response.send_message("Denne ansøgning er allerede behandlet.", ephemeral=True)
            return

        guild = bot.get_guild(GUILD_ID)
        if guild is None:
            await interaction.response.send_message("Kunne ikke finde Discord-serveren.", ephemeral=True)
            return

        invite_channel = guild.get_channel(INVITE_CHANNEL_ID)
        if invite_channel is None:
            await interaction.response.send_message("Invite-kanalen kunne ikke findes.", ephemeral=True)
            return

        try:
            invite = await invite_channel.create_invite(
                max_uses=1,
                max_age=86400,  # 1 dag
                unique=True,
                reason=f"Godkendt Astra SMP ansøgning ({application.minecraft_username})",
            )

            user = await bot.fetch_user(application.discord_user_id)

            dm_embed = discord.Embed(
                title="Du er blevet godkendt til Astra SMP",
                description=(
                    "Din ansøgning er blevet godkendt.\n\n"
                    f"**Invite:** {invite.url}\n\n"
                    "Linket kan bruges **1 gang** og udløber om **1 dag**."
                ),
                color=0x43B581,
            )
            dm_embed.set_footer(text="Hvis linket er udløbet, så kontakt staff.")

            await user.send(embed=dm_embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "Kunne ikke sende DM til brugeren. Bed dem åbne deres DMs og prøv igen.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            logger.exception("Fejl under godkendelse: %s", exc)
            await interaction.response.send_message(
                f"Fejl under godkendelse: {exc}",
                ephemeral=True,
            )
            return

        application.status = "approved"
        application.reviewed_by = interaction.user.id
        store.set(application)

        embed = build_application_embed(application, reviewed_by=interaction.user, decision="Godkendt")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(
            "Ansøgningen er godkendt, og invite er sendt i DM.",
            ephemeral=True,
        )

    @discord.ui.button(label="Afvis", style=discord.ButtonStyle.danger, custom_id="astra:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._is_staff(interaction):
            return

        application = store.get(self.application_id)
        if not application:
            await interaction.response.send_message("Ansøgningen blev ikke fundet.", ephemeral=True)
            return

        if application.status != "pending":
            await interaction.response.send_message("Denne ansøgning er allerede behandlet.", ephemeral=True)
            return

        application.status = "denied"
        application.reviewed_by = interaction.user.id
        store.set(application)

        try:
            user = await bot.fetch_user(application.discord_user_id)
            dm_embed = discord.Embed(
                title="Svar på din Astra SMP ansøgning",
                description="Din ansøgning blev desværre ikke godkendt denne gang.",
                color=0xF04747,
            )
            await user.send(embed=dm_embed)
        except Exception:
            pass

        embed = build_application_embed(application, reviewed_by=interaction.user, decision="Afvist")
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message("Ansøgningen er afvist.", ephemeral=True)


async def handle_apply(request: web.Request) -> web.Response:
    logger.info("Indgående ansøgning fra %s", request.remote)

    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers())

    try:
        payload = await request.json()
    except Exception:
        return json_response({"error": "Ugyldigt JSON payload."}, status=400)

    required = [
        "minecraft_username",
        "discord_user_id",
        "age",
        "playstyle",
        "why_join",
        "experience",
    ]

    missing = [field for field in required if not str(payload.get(field, "")).strip()]
    if missing:
        return json_response({"error": f"Mangler felter: {', '.join(missing)}"}, status=400)

    try:
        discord_user_id = int(str(payload["discord_user_id"]).strip())
    except ValueError:
        return json_response({"error": "Discord user ID skal være et tal."}, status=400)

    application = Application(
        application_id=secrets.token_hex(6),
        minecraft_username=str(payload["minecraft_username"]).strip(),
        discord_user_id=discord_user_id,
        age=str(payload["age"]).strip(),
        playstyle=str(payload["playstyle"]).strip(),
        why_join=str(payload["why_join"]).strip(),
        experience=str(payload["experience"]).strip(),
        extra=str(payload.get("extra", "")).strip(),
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )

    store.set(application)

    channel = bot.get_channel(APPLICATION_CHANNEL_ID)
    if channel is None:
        return json_response({"error": "Ansøgningskanalen kunne ikke findes i botten."}, status=500)

    try:
        embed = build_application_embed(application)
        message = await channel.send(embed=embed, view=DecisionView(application.application_id))
        application.message_id = message.id
        store.set(application)
    except Exception as exc:
        logger.exception("Fejl ved sending til Discord: %s", exc)
        return json_response({"error": "Kunne ikke sende ansøgning til Discord."}, status=500)

    return json_response({"ok": True, "application_id": application.application_id})


async def start_web_app():
    app = web.Application(client_max_size=1024**2)
    app.router.add_route("POST", "/api/apply", handle_apply)
    app.router.add_route("OPTIONS", "/api/apply", handle_apply)

    runner = web.AppRunner(app)
    await runner.setup()

    logger.info("Starter API på host=%s port=%s", WEB_HOST, WEB_PORT)

    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()

    logger.info("API kører på http://%s:%s", WEB_HOST, WEB_PORT)


@bot.event
async def on_ready():
    logger.info("Logget ind som %s", bot.user)

    for app_item in store.pending():
        bot.add_view(DecisionView(app_item.application_id))

    logger.info("Persistent views registreret for %s pending ansøgninger", len(store.pending()))


async def main():
    while True:
        try:
            async with bot:
                await start_web_app()
                await bot.start(DISCORD_TOKEN)
        except Exception as e:
            logger.error("Bot crashed: %s", e)
            logger.info("Retry om 10 sek...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
