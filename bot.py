import discord
from discord.ext import commands
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="k!", intents=intents)

# =========================
# BOT AÇILDIĞINDA
# =========================
@bot.event
async def on_ready():
    print(f"Bot aktif! Giriş yapıldı: {bot.user}")

# =========================
# HATA MESAJLARI
# =========================
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"Hata: {error}")

# =========================
# YARDIM KOMUTU
# =========================
@bot.command()
async def yardım(ctx):
    embed = discord.Embed(title="📌 Komut Listesi", color=0x00ffea)
    embed.add_field(name="🔧 Moderasyon:", 
                    value="k!sil\nk!kick\nk!ban\nk!unban\nk!timeout\nk!untimeout\nk!yavaşmod", inline=False)
    embed.add_field(name="👥 Kullanıcı:", 
                    value="k!avatar\nk!bilgi\nk!sunucu", inline=False)
    embed.add_field(name="⚠ Koruma:", 
                    value="Küfür engel, link engel, reklam engel (otomatik aktif)", inline=False)
    embed.add_field(name="📢 Diğer:", 
                    value="k!duyuru\nk!rolver\nk!rolal", inline=False)
    await ctx.send(embed=embed)

# =========================
# PING
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency*1000)} ms")

# =========================
# MESAJ SİLME
# =========================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def sil(ctx, miktar: int):
    await ctx.channel.purge(limit=miktar+1)
    await ctx.send(f"{miktar} mesaj silindi!", delete_after=3)

# =========================
# KICK
# =========================
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, sebep="Sebep belirtilmedi"):
    await member.kick(reason=sebep)
    await ctx.send(f"{member} sunucudan atıldı!")

# =========================
# BAN
# =========================
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, sebep="Sebep belirtilmedi"):
    await member.ban(reason=sebep)
    await ctx.send(f"{member} sunucudan banlandı!")

# =========================
# UNBAN
# =========================
@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, userid: int):
    user = await bot.fetch_user(userid)
    await ctx.guild.unban(user)
    await ctx.send(f"{user} banı açıldı!")

# =========================
# TIMEOUT
# =========================
@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, saniye: int):
    await member.timeout(discord.utils.utcnow() + discord.timedelta(seconds=saniye))
    await ctx.send(f"{member} {saniye} saniye susturuldu!")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"{member} susturması kaldırıldı!")

# =========================
# YAVAŞ MOD
# =========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def yavaşmod(ctx, saniye: int):
    await ctx.channel.edit(slowmode_delay=saniye)
    await ctx.send(f"Yavaş mod {saniye} saniyeye ayarlandı!")

# =========================
# AVATAR
# =========================
@bot.command()
async def avatar(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(member.avatar.url)

# =========================
# DUYURU
# =========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def duyuru(ctx, *, mesaj):
    embed = discord.Embed(title="📢 DUYURU", description=mesaj, color=0xffcc00)
    await ctx.send("@everyone", embed=embed)

# =========================
# ROL VER / AL
# =========================
@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolver(ctx, member: discord.Member, rol: discord.Role):
    await member.add_roles(rol)
    await ctx.send(f"{member} adlı kullanıcıya {rol} verildi!")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolal(ctx, member: discord.Member, rol: discord.Role):
    await member.remove_roles(rol)
    await ctx.send(f"{member} adlı kullanıcıdan {rol} alındı!")

# =========================
# KÜFÜR ENGEL
# =========================
KUFURLER = [
    "orospu çoçuğu","ananı sikerim ","ananı sikeyim","ananı yatırıp sikeyim"
]

@bot.event
async def on_message(msg):
    if msg.author.bot: 
        return

    # Küfür kontrol
    if any(kufur in msg.content.lower() for kufur in KUFURLER):
        await msg.delete()
        await msg.channel.send(f"{msg.author.mention} küfür yasak!", delete_after=3)

    await bot.process_commands(msg)

# =========================
# TOKEN
# =========================
bot.run(os.getenv("TOKEN"))


