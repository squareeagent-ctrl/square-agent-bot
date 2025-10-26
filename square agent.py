import discord
from discord.ext import commands, tasks
from discord import app_commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os, json, asyncio, logging
import smtplib
from email.message import EmailMessage

# ---------------- CONFIG ---------------- #
CONFIG_FILE = "tournaments_config.json"
MASTER_SHEET_NAME = "Tournaments_All"

DISCORD_TOKEN = "MTM4MjQ1OTI4ODU5Njc3NTA1Mg.G9kZYP.1XHZi2hxt1e7O0_RFWhGTN4VQalHhzW64RfFbw"

ADMIN_EMAIL = "kulkarnishashvat0@gmail.com"
EMAIL_ADDRESS ="squareeagent@gmail.com"
EMAIL_PASSWORD ="hjtj irsm kucd vocq"
SERVICE_ACCOUNT_FILE = "service_account.json" 


# ---------------- LOGGING ---------------- #
logging.basicConfig(level=logging.INFO)

# ---------------- GOOGLE SHEETS ---------------- #
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if os.getenv("service_account.json"):
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.getenv("service_account.json")), scope
    )
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)

client = gspread.authorize(creds)

try:
    master_sheet = client.open(MASTER_SHEET_NAME)
except gspread.SpreadsheetNotFound:
    master_sheet = client.create(MASTER_SHEET_NAME)
    master_sheet.share(creds.service_account_email, perm_type="user", role="writer")

# ---------------- CONFIG STORAGE ---------------- #
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({}, f)

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------- EMAIL ---------------- #
def send_email(subject, body, to):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        logging.info(f"📧 Email sent to {to}")
    except Exception as e:
        logging.error(f"❌ Email Error: {e}")

# ---------------- DISCORD BOT ---------------- #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

reminders = []

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")
    reminder_loop.start()

# ---------------- TOURNAMENT COMMANDS ---------------- #
@bot.tree.command(name="new_tournament", description="Create a new tournament")
async def new_tournament(interaction: discord.Interaction, name: str, max_teams: int = 300, teams_per_group: int = 20):
    try:
        config = load_config()
        guild_id = str(interaction.guild_id)

        try:
            master_sheet.worksheet(name)
            await interaction.response.send_message(f"⚠️ Tournament **{name}** already exists.", ephemeral=True)
            return
        except gspread.WorksheetNotFound:
            ws = master_sheet.add_worksheet(title=name, rows="1000", cols="10")
            ws.update([["Timestamp","Team","Captain","Email","P1","P2","P3","P4","Status","Group"]])

        category = await interaction.guild.create_category(f"🎮 {name}")
        announce_channel = await interaction.guild.create_text_channel("📢-announcements", category=category)
        reg_channel = await interaction.guild.create_text_channel("📝-registrations", category=category)
        results_channel = await interaction.guild.create_text_channel("🏆-results", category=category)
        help_channel = await interaction.guild.create_text_channel("❓-help-desk", category=category)

        if guild_id not in config: config[guild_id] = {}
        config[guild_id][name] = {
            "announce_channel": announce_channel.id,
            "results_channel": results_channel.id,
            "helpdesk_channel": help_channel.id,
            "max_teams": max_teams,
            "teams_per_group": teams_per_group
        }
        save_config(config)

        await interaction.response.send_message(f"✅ Tournament **{name}** created successfully!")
    except Exception as e:
        logging.error(f"❌ Error creating tournament: {e}")
        await interaction.response.send_message("❌ Failed to create tournament.", ephemeral=True)

@bot.tree.command(name="register", description="Register a team for a tournament")
async def register(interaction: discord.Interaction, tournament: str, team: str, captain: str, captain_email: str,
                   p1: str, p2: str, p3: str, p4: str):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild_id)
    config = load_config()

    if guild_id not in config or tournament not in config[guild_id]:
        await interaction.followup.send("❌ Tournament not found.", ephemeral=True)
        return

    try:
        t_data = config[guild_id][tournament]
        ws = master_sheet.worksheet(tournament)
        records = ws.get_all_records()

        if len(records) >= t_data["max_teams"]:
            await interaction.followup.send("❌ Tournament slots are full!", ephemeral=True)
            return

        group_number = (len(records)//t_data["teams_per_group"]) + 1
        group_name = f"Group {group_number}"
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        ws.append_row([ts, team, captain, captain_email, p1, p2, p3, p4, "Confirmed", group_name])

        announce_channel = bot.get_channel(t_data["announce_channel"])
        if announce_channel:
            await announce_channel.send(f"🏆 **New Team Registered in {tournament}**\nTeam: **{team}** | Captain: {captain} | Group: **{group_name}**")

        subject = f"Tournament Registration Confirmed: {team}"
        body = f"🎮 Tournament: {tournament}\nTeam: {team}\nCaptain: {captain}\nPlayers: {p1}, {p2}, {p3}, {p4}\nGroup: {group_name}\n✅ Status: Confirmed"
        send_email(subject, body, captain_email)
        send_email(subject, body, ADMIN_EMAIL)

        await interaction.followup.send(f"✅ Team **{team}** registered under **{group_name}**. Email sent to {captain_email}", ephemeral=True)
    except Exception as e:
        logging.error(f"❌ Registration Error: {e}")
        await interaction.followup.send("❌ Registration failed.", ephemeral=True)

# ---------------- COMMUNITY COMMANDS ---------------- #
@bot.tree.command(name="announce", description="Send an announcement to a tournament's channel")
async def announce(interaction: discord.Interaction, tournament: str, message: str):
    config = load_config()
    guild_id = str(interaction.guild_id)
    if guild_id not in config or tournament not in config[guild_id]:
        await interaction.response.send_message("❌ Tournament not found.", ephemeral=True)
        return
    channel = bot.get_channel(config[guild_id][tournament]["announce_channel"])
    if channel:
        await channel.send(f"📢 **Announcement for {tournament}:**\n{message}")
        await interaction.response.send_message("✅ Announcement sent.", ephemeral=True)

@bot.tree.command(name="poll", description="Create a quick poll")
async def poll(interaction: discord.Interaction, question: str, option1: str, option2: str):
    msg = await interaction.response.send_message(f"📊 **{question}**\n1️⃣ {option1}\n2️⃣ {option2}")
    sent_msg = await interaction.original_response()
    await sent_msg.add_reaction("1️⃣")
    await sent_msg.add_reaction("2️⃣")

@bot.tree.command(name="remind", description="Set a reminder in minutes")
async def remind(interaction: discord.Interaction, message: str, minutes: int):
    remind_time = datetime.utcnow() + timedelta(minutes=minutes)
    reminders.append((interaction.channel.id, message, remind_time))
    await interaction.response.send_message(f"⏰ Reminder set for {minutes} minutes from now.", ephemeral=True)

@tasks.loop(seconds=30)
async def reminder_loop():
    now = datetime.utcnow()
    for r in reminders[:]:
        channel_id, msg, remind_time = r
        if now >= remind_time:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"⏰ Reminder: {msg}")
            reminders.remove(r)

@bot.tree.command(name="survey", description="Collect feedback and save to Google Sheets")
async def survey(interaction: discord.Interaction, tournament: str, feedback: str):
    try:
        ws = master_sheet.worksheet(tournament)
        ws.append_row([datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "Feedback", interaction.user.name, feedback])
        await interaction.response.send_message("✅ Feedback recorded. Thanks!", ephemeral=True)
    except Exception as e:
        logging.error(f"Survey error: {e}")
        await interaction.response.send_message("❌ Failed to record feedback.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show registered teams count per group")
async def leaderboard(interaction: discord.Interaction, tournament: str):
    try:
        ws = master_sheet.worksheet(tournament)
        records = ws.get_all_records()
        groups = {}
        for r in records:
            groups[r["Group"]] = groups.get(r["Group"], 0) + 1
        text = "🏆 **Leaderboard**\n"
        for g, count in groups.items():
            text += f"{g}: {count} teams\n"
        await interaction.response.send_message(text, ephemeral=True)
    except Exception as e:
        logging.error(f"Leaderboard error: {e}")
        await interaction.response.send_message("❌ Failed to fetch leaderboard.", ephemeral=True)

@bot.tree.command(name="help", description="Show help menu for Square Agent")
async def help_cmd(interaction: discord.Interaction):
    help_text = (
        "📖 **Square Agent Commands**\n\n"
        "🎮 Tournament:\n"
        "  • `/new_tournament` – Create tournament\n"
        "  • `/register` – Register team\n"
        "  • `/leaderboard` – Show groups\n\n"
        "📢 Community:\n"
        "  • `/announce` – Tournament announcement\n"
        "  • `/poll` – Create poll\n"
        "  • `/remind` – Set reminder\n"
        "  • `/survey` – Submit feedback\n\n"
        "❓ Support:\n"
        "  • `/help` – Show help\n"
        "  • `/contact` – Contact admin"
    )
    await interaction.response.send_message(help_text, ephemeral=True)

@bot.tree.command(name="contact", description="Contact the admin")
async def contact(interaction: discord.Interaction, message: str):
    try:
        subject = f"Contact from {interaction.user}"
        body = f"User: {interaction.user}\nMessage:\n{message}"
        send_email(subject, body, ADMIN_EMAIL)
        await interaction.response.send_message("✅ Your message has been sent to the admin!", ephemeral=True)
    except Exception as e:
        logging.error(f"❌ Contact Error: {e}")
        await interaction.response.send_message("❌ Failed to send message.", ephemeral=True)

# ---------------- RUN ---------------- #
bot.run(DISCORD_TOKEN)

