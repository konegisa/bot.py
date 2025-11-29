import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import timedelta, datetime, timezone

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)



# -------------------------------
# BOT AÇILDIĞINDA
# -------------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot aktif! Giriş yapıldı: {bot.user}")
    print("Slash komutları senkronize edildi.")


# -------------------------------
# YARDIM
# -------------------------------
@bot.tree.command(name="yardım", description="Komut listesini gösterir.")
async def yardım(interaction: discord.Interaction):
    embed = discord.Embed(title="📌 Slash Komut Listesi", color=0x00ffea)
    embed.add_field(name="🔧 Moderasyon",
        value="/sil\n/kick\n/ban\n/unban\n/timeout\n/untimeout\n/slowmode",
        inline=False)

    embed.add_field(name="👥 Kullanıcı", value="/avatar\n/kullanıcıbilgi\n/sunucu", inline=False)
    embed.add_field(name="🎭 Roller", value="/rolver\n/rolal", inline=False)
    embed.add_field(name="🟡 Diğer", value="/duyuru", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------------------
# MESAJ SİLME
# -------------------------------
@bot.tree.command(name="sil", description="Belirtilen miktarda mesaj siler.")
@app_commands.checks.has_permissions(manage_messages=True)
async def sil(interaction: discord.Interaction, miktar: int):
    await interaction.channel.purge(limit=miktar)
    await interaction.response.send_message(f"{miktar} mesaj silindi!", ephemeral=True)


# -------------------------------
# KICK
# -------------------------------
@bot.tree.command(name="kick", description="Bir kullanıcıyı atar.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, sebep: str = "Sebep belirtilmedi"):
    await member.kick(reason=sebep)
    await interaction.response.send_message(f"{member} sunucudan atıldı!")


# -------------------------------
# BAN
# -------------------------------
@bot.tree.command(name="ban", description="Bir kullanıcıyı banlar.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, sebep: str = "Sebep belirtilmedi"):
    await member.ban(reason=sebep)
    await interaction.response.send_message(f"{member} banlandı!")


# -------------------------------
# UNBAN
# -------------------------------
@bot.tree.command(name="unban", description="Bir kullanıcının banını açar.")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"{user} banı açıldı!")


# -------------------------------
# TIMEOUT
# -------------------------------
@bot.tree.command(name="timeout", description="Bir kullanıcıya timeout verir.")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, saniye: int):
    until = datetime.now(timezone.utc) + timedelta(seconds=saniye)
    await member.timeout(until)
    await interaction.response.send_message(f"{member} {saniye} saniye timeoutlandı!")


@bot.tree.command(name="untimeout", description="Bir kullanıcının timeout'unu kaldırır.")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"{member} timeout kaldırıldı!")


# -------------------------------
# YAVAŞ MOD
# -------------------------------
@bot.tree.command(name="slowmode", description="Kanal yavaş modunu ayarlar.")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, saniye: int):
    await interaction.channel.edit(slowmode_delay=saniye)
    await interaction.response.send_message(f"Yavaş mod {saniye} saniye olarak ayarlandı!")


# -------------------------------
# AVATAR
# -------------------------------
@bot.tree.command(name="avatar", description="Bir kullanıcının avatarını gösterir.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    await interaction.response.send_message(member.avatar.url)


# -------------------------------
# DUYURU
# -------------------------------
@bot.tree.command(name="duyuru", description="Duyuru gönderir.")
@app_commands.checks.has_permissions(manage_channels=True)
async def duyuru(interaction: discord.Interaction, mesaj: str):
    embed = discord.Embed(title="📢 DUYURU", description=mesaj, color=0xffcc00)
    await interaction.response.send_message("@everyone", embed=embed)


# -------------------------------
# ROL VER / AL
# -------------------------------
@bot.tree.command(name="rolver", description="Bir kullanıcıya rol verir.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rolver(interaction: discord.Interaction, member: discord.Member, rol: discord.Role):
    await member.add_roles(rol)
    await interaction.response.send_message(f"{member} kullanıcısına {rol} verildi!")


@bot.tree.command(name="rolal", description="Bir kullanıcıdan rol alır.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rolal(interaction: discord.Interaction, member: discord.Member, rol: discord.Role):
    await member.remove_roles(rol)
    await interaction.response.send_message(f"{member} kullanıcısından {rol} alındı!")


# -------------------------------
# KÜFÜR ENGEL
# -------------------------------
KUFURLER = ["orospu", "sikerim", "piç", "amk", "yarrak", "ananı"]

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    if any(kufur in msg.content.lower() for kufur in KUFURLER):
        await msg.delete()
        await msg.channel.send(f"{msg.author.mention} küfür yasak!", delete_after=3)

    await bot.process_commands(msg)  # <-- BUNU EKLE



# -------------------------------
# TOKEN
# -------------------------------
bot.run(os.getenv("TOKEN"))







