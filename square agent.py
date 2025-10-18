import discord
from discord import app_commands
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import logging
import smtplib
from email.message import EmailMessage
import math


DISCORD_TOKEN = "MTM4MjQ1OTI4ODU5Njc3NTA1Mg.GPAe0X.ttD3iMH8qLN-UPYe4Xpb6bHM9nCj8Wmz_XYKBo"
ADMIN_EMAIL = "kulkarnishashvat0@gmail.com"
SHEET_NAME = "Tournament Registrations"
EMAIL_ADDRESS = "squareeagent@gmail.com"
EMAIL_PASSWORD = "pihp hmvp tocq zjhr"  
WELCOME_CHANNEL_ID = 1429040279947837450
ANNOUNCE_CHANNEL_ID = 1429056011758469220
TEAMS_PER_GROUP = 20
MAX_TEAMS = 300



scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
logging.basicConfig(level=logging.INFO)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"👋 Welcome {member.mention}! 🎮 Get ready for the BGMI Tournament!")


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


@bot.tree.command(name="register", description="Register your BGMI team for the tournament.")
@app_commands.describe(
    team="Team name",
    captain="Captain name",
    captain_email="Captain email",
    p1="Player 1",
    p2="Player 2",
    p3="Player 3",
    p4="Player 4"
)
async def register(interaction: discord.Interaction, team: str, captain: str, captain_email: str, p1: str, p2: str, p3: str, p4: str):
    await interaction.response.defer(ephemeral=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        records = sheet.get_all_records()
        team_count = len(records)
        if team_count >= MAX_TEAMS:
            await interaction.followup.send("❌ All 300 slots are full. Registration closed!", ephemeral=True)
            return

        group_number = math.floor(team_count / TEAMS_PER_GROUP) + 1
        group_name = f"Group {group_number}"

        data = [timestamp, team, captain, captain_email, p1, p2, p3, p4, group_name, "Confirmed"]
        sheet.append_row(data)

        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=group_name)
        if not role:
            role = await guild.create_role(name=group_name)
        await interaction.user.add_roles(role)

        subject = f"Tournament Registration Confirmed: {team} ({group_name})"
        body = (
            f"🎮 BGMI Tournament Registration Successful!\n\n"
            f"Team Name: {team}\n"
            f"Captain: {captain}\n"
            f"Captain Email: {captain_email}\n"
            f"Players: {p1}, {p2}, {p3}, {p4}\n"
            f"Assigned Group: {group_name}\n"
            f"Status: ✅ Confirmed\n"
            f"Time: {timestamp}\n\n"
            f"Thank you for registering with Square Agent!"
        )

        send_email(subject, body, ADMIN_EMAIL)
        send_email(subject, body, captain_email)

        announce_channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if announce_channel:
            await announce_channel.send(
                f"🎉 **New Team Registered!**\n"
                f"Team: **{team}**\n"
                f"Captain: **{captain}**\n"
                f"Players: {p1}, {p2}, {p3}, {p4}\n"
                f"Group: **{group_name}**\n"
                f"Status: ✅ Confirmed"
            )

        await interaction.followup.send(
            f"✅ Team **{team}** registered & confirmed!\n"
            f"🏷️ Assigned to **{group_name}**.\n"
            f"📩 Confirmation email sent to {captain_email}.",
            ephemeral=True
        )

    except Exception as e:
        logging.error(f"❌ Registration Error: {e}")
        await interaction.followup.send("❌ Registration failed. Please try again later.", ephemeral=True)


@bot.tree.command(name="checkslot", description="Check how many slots are left in the tournament.")
async def checkslot(interaction: discord.Interaction):
    try:
        records = sheet.get_all_records()
        team_count = len(records)
        slots_left = MAX_TEAMS - team_count
        await interaction.response.send_message(
            f"📊 **Current Registrations:** {team_count}/300 teams\n"
            f"🟢 **Slots Left:** {slots_left}",
            ephemeral=True
        )
    except Exception as e:
        logging.error(f"❌ Slot Check Error: {e}")
        await interaction.response.send_message("❌ Could not fetch slot info.", ephemeral=True)

        
@bot.tree.command(name="listgroups", description="List all groups and their registered teams.")
async def listgroups(interaction: discord.Interaction):
    try:
        records = sheet.get_all_records()
        if not records:
            await interaction.response.send_message("📋 No teams registered yet.", ephemeral=True)
            return

 
        groups = {}
        for record in records:
            group = record.get("Group", "Unknown")
            team_name = record.get("Team", "Unnamed")
            if group not in groups:
                groups[group] = []
            groups[group].append(team_name)

  
        msg = "📋 **Tournament Groups & Teams:**\n\n"
        for group, teams in sorted(groups.items()):
            msg += f"**{group}** ({len(teams)} teams):\n"
            for t in teams:
                msg += f"- {t}\n"
            msg += "\n"

 
        for chunk in [msg[i:i+1900] for i in range(0, len(msg), 1900)]:
            await interaction.followup.send(chunk, ephemeral=True)

    except Exception as e:
        logging.error(f"❌ List Groups Error: {e}")
        await interaction.response.send_message("❌ Failed to fetch group list.", ephemeral=True)

bot.run(DISCORD_TOKEN)
