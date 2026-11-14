import discord
from discord import app_commands
from discord.ext import commands

import os
import random
import asyncio
import yt_dlp
import sqlite3
import time

from datetime import timedelta, datetime, timezone


# ============================================================
# ENV / AYARLAR
# ============================================================

BOT_TOKEN = "MTQ1NzA3MzI5OTkzMzc1NzQ5MA.GN3PRI.qxMSJTh76Emhnajy0QGB7YhkrbVV7A3vvqRShA"

PREFIX = "!"

BOT_NAME = "VELORIA"
PURPLE = discord.Color.from_rgb(91, 33, 182)


# ============================================================
# FFMPEG BUL
# ============================================================

HOME = os.path.expanduser("~")

FFMPEG_ADAYLARI = [
    os.path.join(
        HOME,
        "Desktop",
        "ffmpeg-9.0.1-essentials_build",
        "ffmpeg-9.0.1-essentials_build",
        "bin",
        "ffmpeg.exe"
    ),

    os.path.join(
        HOME,
        "Desktop",
        "ffmpeg-9.0.1-essentials_build",
        "bin",
        "ffmpeg.exe"
    ),

    os.path.join(
        HOME,
        "Desktop",
        "ffmpeg",
        "bin",
        "ffmpeg.exe"
    ),

    r"C:\ffmpeg\bin\ffmpeg.exe"
]

FFMPEG_PATH = None

for yol in FFMPEG_ADAYLARI:
    if os.path.isfile(yol):
        FFMPEG_PATH = yol
        break

# Linux hosting ortamlarında imageio-ffmpeg paketinin indirdiği FFmpeg'i kullan.
# Paket kurulu değilse mevcut Windows/Linux aday yolları kullanılmaya devam eder.
if not FFMPEG_PATH:
    try:
        import imageio_ffmpeg
        aday_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if aday_ffmpeg and os.path.isfile(aday_ffmpeg):
            FFMPEG_PATH = aday_ffmpeg
    except Exception:
        pass


# ============================================================
# DISCORD
# ============================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)


# ============================================================
# OPUS (LINUX HOSTING)
# ============================================================

# Hostrix gibi root yetkisi olmayan Linux hostinglerde kullanıcı dizinine
# çıkarılan libopus kütüphanesini bot başlarken yükle.
OPUS_PATH = os.path.join(
    HOME,
    ".local",
    "lib",
    "opus",
    "usr",
    "lib",
    "x86_64-linux-gnu",
    "libopus.so.0"
)

if os.path.isfile(OPUS_PATH):
    try:
        discord.opus.load_opus(OPUS_PATH)
        print("[OPUS] Linux kütüphanesi yüklendi.")
    except Exception as e:
        print("[OPUS] Kütüphane yüklenemedi:", e)
else:
    print("[OPUS] Kullanıcı dizininde Linux kütüphanesi bulunamadı; sistem Opus'u kullanılacak.")


# ============================================================
# SQLITE
# ============================================================

DB_PATH = "veloria.db"

db = sqlite3.connect(
    DB_PATH,
    check_same_thread=False
)

cursor = db.cursor()


def db_execute(query, params=(), commit=True):
    cursor.execute(query, params)

    if commit:
        db.commit()

    return cursor


# ============================================================
# DASHBOARD BAĞLANTISI
# ============================================================

DASHBOARD_CACHE = {}
DASHBOARD_CACHE_TIME = {}

SPAM_MESSAGES = {}
RAID_JOINS = {}


def dashboard_settings(guild_id):

    simdi = time.time()

    son_okuma = DASHBOARD_CACHE_TIME.get(
        guild_id,
        0
    )

    if (
        guild_id in DASHBOARD_CACHE
        and simdi - son_okuma < 5
    ):
        return DASHBOARD_CACHE[guild_id]

    try:

        con = sqlite3.connect(
            DB_PATH,
            timeout=10
        )

        cur = con.cursor()

        cur.execute(
            """
            SELECT
                anti_spam,
                anti_link,
                anti_raid,
                profanity_filter,
                log_channel,
                welcome_channel,
                autorole
            FROM dashboard_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        )

        row = cur.fetchone()

        con.close()

        if not row:

            ayarlar = {
                "anti_spam": 0,
                "anti_link": 0,
                "anti_raid": 0,
                "profanity_filter": 0,
                "log_channel": 0,
                "welcome_channel": 0,
                "autorole": 0
            }

        else:

            ayarlar = {
                "anti_spam": row[0],
                "anti_link": row[1],
                "anti_raid": row[2],
                "profanity_filter": row[3],
                "log_channel": row[4],
                "welcome_channel": row[5],
                "autorole": row[6]
            }

        DASHBOARD_CACHE[guild_id] = ayarlar
        DASHBOARD_CACHE_TIME[guild_id] = simdi

        return ayarlar

    except Exception as e:

        print(
            "DASHBOARD AYAR OKUMA HATASI:",
            e
        )

        return {
            "anti_spam": 0,
            "anti_link": 0,
            "anti_raid": 0,
            "profanity_filter": 0,
            "log_channel": 0,
            "welcome_channel": 0,
            "autorole": 0
        }


async def dashboard_log(guild, mesaj):

    if not guild:
        return

    ayarlar = dashboard_settings(
        guild.id
    )

    kanal_id = ayarlar.get(
        "log_channel",
        0
    )

    if not kanal_id:
        return

    kanal = guild.get_channel(
        int(kanal_id)
    )

    if not kanal:
        return

    try:

        await kanal.send(
            mesaj
        )

    except discord.Forbidden:

        print(
            "[LOG] Botun log kanalına mesaj gönderme yetkisi yok."
        )

    except Exception as e:

        print(
            "[LOG] Log gönderme hatası:",
            e
        )


# ============================================================
# KÜFÜR FİLTRESİ
# ============================================================

YASAKLI_KELIMELER = {
    "amk",
    "aq",
    "siktir",
    "orospu",
    "piç",
    "salak",
    "şerefsiz",
    "gerizekalı"
}


def kufur_var_mi(metin):

    temiz = (
        metin.lower()
        .replace(".", " ")
        .replace(",", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace("*", "")
        .replace("_", " ")
        .replace("-", " ")
    )

    kelimeler = set(
        temiz.split()
    )

    return bool(
        kelimeler.intersection(
            YASAKLI_KELIMELER
        )
    )


# ============================================================
# LINK FİLTRESİ
# ============================================================

LINK_ISARETLERI = (
    "http://",
    "https://",
    "www.",
    "discord.gg/",
    "discord.com/invite/"
)


def link_var_mi(metin):

    metin = metin.lower()

    return any(
        x in metin
        for x in LINK_ISARETLERI
    )


# ============================================================
# SQLITE TABLOLARI
# ============================================================

db_execute("""
CREATE TABLE IF NOT EXISTS balances (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 0
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER,
    moderator_id INTEGER,
    reason TEXT,
    created_at INTEGER
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS afk (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    created_at INTEGER
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    log_channel INTEGER DEFAULT 0,
    welcome_channel INTEGER DEFAULT 0,
    goodbye_channel INTEGER DEFAULT 0,
    autorole INTEGER DEFAULT 0
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS autoresponses (
    guild_id INTEGER,
    trigger TEXT,
    response TEXT
)
""")


# ============================================================
# VERİLER
# ============================================================

muzik_kuyruklari = {}
muzik_ayarlar = {}
muzik_panelleri = {}

XP_COOLDOWN = {}

otomatik_muzik = {}
radio_dil = {}
radio_gecmisi = {}

giveaways = {}
tickets = {}

message_stats = {}
voice_stats = {}


# ============================================================
# PARA
# ============================================================

def get_balance(user_id):

    row = db_execute(
        "SELECT money FROM balances WHERE user_id = ?",
        (user_id,),
        commit=False
    ).fetchone()

    if not row:

        db_execute(
            "INSERT INTO balances (user_id, money) VALUES (?, ?)",
            (user_id, 0)
        )

        return 0

    return row[0]


def add_balance(user_id, miktar):

    bakiye = get_balance(user_id)

    yeni = bakiye + miktar

    db_execute(
        "UPDATE balances SET money = ? WHERE user_id = ?",
        (yeni, user_id)
    )

    return yeni


# ============================================================
# XP
# ============================================================

def get_xp(user_id):

    row = db_execute(
        "SELECT xp, level FROM xp WHERE user_id = ?",
        (user_id,),
        commit=False
    ).fetchone()

    if not row:

        db_execute(
            "INSERT INTO xp (user_id, xp, level) VALUES (?, ?, ?)",
            (user_id, 0, 1)
        )

        return {
            "xp": 0,
            "level": 1
        }

    return {
        "xp": row[0],
        "level": row[1]
    }


def xp_ekle(user_id, miktar):

    data = get_xp(user_id)

    data["xp"] += miktar

    gereken = data["level"] * 100

    seviye_atladi = False

    while data["xp"] >= gereken:

        data["xp"] -= gereken
        data["level"] += 1

        gereken = data["level"] * 100

        seviye_atladi = True

    db_execute(
        """
        UPDATE xp
        SET xp = ?, level = ?
        WHERE user_id = ?
        """,
        (
            data["xp"],
            data["level"],
            user_id
        )
    )

    return seviye_atladi


# ============================================================
# SÜRE
# ============================================================

def format_duration(seconds):

    if not seconds:
        return "Bilinmiyor"

    try:
        seconds = int(seconds)

    except Exception:
        return "Bilinmiyor"

    saat = seconds // 3600
    dakika = (seconds % 3600) // 60
    saniye = seconds % 60

    if saat > 0:
        return f"{saat}:{dakika:02d}:{saniye:02d}"

    return f"{dakika}:{saniye:02d}"


# ============================================================
# MÜZİK AYARLARI
# ============================================================

def get_settings(guild_id):

    if guild_id not in muzik_ayarlar:

        muzik_ayarlar[guild_id] = {
            "volume": 0.50,
            "loop": False
        }

    return muzik_ayarlar[guild_id]


# ============================================================
# KUYRUK
# ============================================================

def get_queue(guild_id):

    if guild_id not in muzik_kuyruklari:

        muzik_kuyruklari[guild_id] = []

    return muzik_kuyruklari[guild_id]


# ============================================================
# YTDLP
# ============================================================

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn"
}


YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0"
}


# ============================================================
# YOUTUBE ARAMA
# ============================================================

def muzik_ara(query):

    try:

        with yt_dlp.YoutubeDL(
            YTDLP_OPTIONS
        ) as ydl:

            info = ydl.extract_info(
                query,
                download=False
            )

            if not info:
                return None

            if "entries" in info:

                entries = info.get(
                    "entries"
                )

                if not entries:
                    return None

                info = entries[0]

            return {
                "title": info.get(
                    "title",
                    "Bilinmeyen Şarkı"
                ),
                "url": info.get("url"),
                "webpage_url": info.get(
                    "webpage_url",
                    info.get(
                        "original_url",
                        ""
                    )
                ),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get(
                    "uploader",
                    "Bilinmeyen Sanatçı"
                )
            }

    except Exception as e:

        print(
            "YOUTUBE ARAMA HATASI:",
            e
        )

        return None


# ============================================================
# ÇOKLU ARAMA
# ============================================================

def muzik_ara_liste(query, adet=20):

    try:

        options = dict(
            YTDLP_OPTIONS
        )

        options["default_search"] = f"ytsearch{adet}"

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                query,
                download=False
            )

            if not info:
                return []

            entries = info.get(
                "entries",
                []
            )

            sonuc = []

            for item in entries:

                if not item:
                    continue

                webpage_url = item.get(
                    "webpage_url",
                    item.get(
                        "original_url",
                        ""
                    )
                )

                if not webpage_url:
                    continue

                title = item.get(
                    "title",
                    "Bilinmeyen Şarkı"
                )

                if "#shorts" in title.lower():
                    continue

                sonuc.append({
                    "title": title,
                    "url": item.get("url"),
                    "webpage_url": webpage_url,
                    "duration": item.get("duration"),
                    "thumbnail": item.get("thumbnail"),
                    "uploader": item.get(
                        "uploader",
                        "Bilinmeyen Sanatçı"
                    )
                })

            return sonuc

    except Exception as e:

        print(
            "RADYO ARAMA HATASI:",
            e
        )

        return []


# ============================================================
# TÜRKÇE ALGILAMA
# ============================================================

TURKCE_KELIMELER = {
    "şarkı",
    "sarki",
    "türkçe",
    "turkce",
    "türkiye",
    "turkiye",
    "pop",
    "arabesk",
    "rap",
    "halk",
    "ilahi",
    "slow",
    "oynat",
    "dinle",
    "klip"
}


TURKCE_SANATCILAR = {
    "manifest",
    "motive",
    "uzi",
    "ceza",
    "sagopa",
    "sagopa kajmer",
    "ezhel",
    "sefo",
    "çakal",
    "cakal",
    "batuflex",
    "lvbel c5",
    "murda",
    "contra",
    "ben fero",
    "mabel matiz",
    "tarkan",
    "hadise",
    "demet akalın",
    "sertab erener",
    "sezen aksu",
    "mor ve ötesi",
    "duman",
    "athena",
    "manga",
    "emir can iğrek",
    "melike şahin",
    "güneş",
    "derya uluğ",
    "irem derici",
    "simge",
    "yıldız tilbe",
    "ferdi tayfur",
    "müslüm gürses",
    "barış manço",
    "teoman",
    "şebnem ferah"
}


def turkce_mi(query, song):

    metin = (
        f"{query} "
        f"{song.get('title', '')} "
        f"{song.get('uploader', '')}"
    ).lower()

    for sanatci in TURKCE_SANATCILAR:

        if sanatci.lower() in metin:
            return True

    turkce_karakterler = "çğıöşü"

    if any(
        karakter in metin
        for karakter in turkce_karakterler
    ):
        return True

    kelimeler = set(
        metin
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )

    return bool(
        kelimeler.intersection(
            TURKCE_KELIMELER
        )
    )


# ============================================================
# RADYO
# ============================================================

TURKCE_RADYO_ARALARI = [
    "Türkçe pop şarkıları",
    "Türkçe rap şarkıları",
    "Türkçe hit şarkılar",
    "Türkçe müzik",
    "Türkçe pop hit",
    "Türkçe rap hit",
    "Türkçe şarkılar 2026",
    "Türkçe pop 2026",
    "Türkçe rap 2026"
]


YABANCI_RADYO_ARALARI = [
    "popular songs",
    "international hit songs",
    "popular English songs",
    "global hit songs",
    "best pop songs",
    "popular music",
    "international pop hits",
    "top songs",
    "hit songs 2026",
    "popular songs 2026"
]


async def otomatik_sarki_bul(guild):

    guild_id = guild.id

    dil = radio_dil.get(
        guild_id
    )

    if not dil:
        return None

    gecmis = radio_gecmisi.setdefault(
        guild_id,
        []
    )

    if dil == "turkce":

        arama_listesi = TURKCE_RADYO_ARALARI

    else:

        arama_listesi = YABANCI_RADYO_ARALARI

    arama = random.choice(
        arama_listesi
    )

    sarkilar = await asyncio.to_thread(
        muzik_ara_liste,
        arama,
        20
    )

    if not sarkilar:
        return None

    yeni_sarkilar = [
        sarki
        for sarki in sarkilar
        if sarki["webpage_url"] not in gecmis
    ]

    if not yeni_sarkilar:

        gecmis.clear()

        yeni_sarkilar = sarkilar

    secilen = random.choice(
        yeni_sarkilar
    )

    gecmis.append(
        secilen["webpage_url"]
    )

    if len(gecmis) > 50:
        del gecmis[:-50]

    print(
        f"[RADYO] "
        f"{'TÜRKÇE' if dil == 'turkce' else 'YABANCI'} "
        f"-> {secilen['title']}"
    )

    return secilen


# ============================================================
# PROGRESS BAR
# ============================================================

def progress_bar(
    position,
    duration,
    uzunluk=18
):

    if not duration or duration <= 0:
        return "━━━━━━━━━━━━━━━━━━"

    oran = min(
        max(position / duration, 0),
        1
    )

    dolu = int(
        oran * uzunluk
    )

    bos = uzunluk - dolu

    if dolu <= 0:

        return (
            "●"
            + "━" * (uzunluk - 1)
        )

    if dolu >= uzunluk:

        return (
            "━" * (uzunluk - 1)
            + "●"
        )

    return (
        "━" * dolu
        + "●"
        + "━" * (bos - 1)
    )


# ============================================================
# MÜZİK EMBED
# ============================================================

def muzik_embed(guild):

    queue = get_queue(
        guild.id
    )

    settings = get_settings(
        guild.id
    )

    embed = discord.Embed(
        color=PURPLE
    )

    embed.set_author(
        name=f"{BOT_NAME} • MUSIC"
    )

    if not queue:

        embed.title = "🎵 Müzik Sistemi"

        embed.description = (
            f"## 💜 {BOT_NAME} Music\n\n"
            "Şu anda hiçbir şarkı çalmıyor.\n\n"
            "🎧 Bir şarkı başlatmak için:\n"
            "`/play şarkı adı`\n\n"
            "────────────────────\n"
            "🎶 **Spotify Style Music Panel**"
        )

        embed.set_footer(
            text=f"{BOT_NAME} • MUSIC"
        )

        return embed

    current = queue[0]

    title = current.get(
        "title",
        "Bilinmeyen Şarkı"
    )

    uploader = current.get(
        "uploader",
        "Bilinmeyen Sanatçı"
    )

    duration = current.get(
        "duration"
    )

    volume = int(
        settings["volume"] * 100
    )

    loop = (
        "Açık 🔁"
        if settings["loop"]
        else "Kapalı"
    )

    radio = (
        "Açık 📻"
        if otomatik_muzik.get(
            guild.id,
            False
        )
        else "Kapalı"
    )

    embed.title = "🎧 Şimdi Çalıyor"

    if current.get("webpage_url"):

        embed.description = (
            f"## [{title}]"
            f"({current['webpage_url']})\n"
            f"**{uploader}**\n\n"
            f"`0:00` "
            f"{progress_bar(0, duration)} "
            f"`{format_duration(duration)}`\n\n"
            f"🎶 **Kuyruk:** "
            f"`{max(0, len(queue) - 1)}` şarkı\n"
            f"🔊 **Ses:** `{volume}%`\n"
            f"🔁 **Döngü:** `{loop}`\n"
            f"📻 **Otomatik:** `{radio}`"
        )

    thumbnail = current.get(
        "thumbnail"
    )

    if thumbnail:

        try:

            embed.set_thumbnail(
                url=thumbnail
            )

        except Exception:
            pass

    embed.set_footer(
        text=(
            "⏮ Önceki • "
            "⏯ Oynat • "
            "⏭ Sonraki • "
            "🔊 Ses"
        )
    )

    return embed


# ============================================================
# PANEL GÜNCELLE
# ============================================================

async def muzik_panel_guncelle(guild):

    message = muzik_panelleri.get(
        guild.id
    )

    if not message:
        return

    try:

        await message.edit(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )

    except discord.NotFound:

        muzik_panelleri.pop(
            guild.id,
            None
        )

    except Exception as e:

        print(
            "PANEL GÜNCELLEME HATASI:",
            e
        )


# ============================================================
# ŞARKI OYNAT
# ============================================================

def ses_urlini_al(webpage_url):
    """YouTube ses URL'sini event loop'u bloklamadan alınabilmesi için senkron çözer."""
    with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
        info = ydl.extract_info(
            webpage_url,
            download=False
        )

        if info and "entries" in info:
            entries = info.get("entries") or []
            info = entries[0] if entries else None

        return info.get("url") if info else None


async def sonraki_sarki(guild):

    guild_id = guild.id

    queue = get_queue(
        guild_id
    )

    voice = guild.voice_client

    if not voice or not voice.is_connected():

        print(
            f"[MÜZİK] {guild.name} -> Ses bağlantısı yok."
        )

        return

    # --------------------------------------------------------
    # KUYRUK BOŞSA OTOMATİK RADYO
    # --------------------------------------------------------

    if not queue and otomatik_muzik.get(
        guild_id,
        False
    ):

        yeni_sarki = None

        # En fazla 3 kez arama yap
        for deneme in range(3):

            try:

                yeni_sarki = await otomatik_sarki_bul(
                    guild
                )

            except Exception as e:

                print(
                    f"[RADYO] Şarkı arama hatası "
                    f"(deneme {deneme + 1}):",
                    e
                )

                yeni_sarki = None

            if yeni_sarki:
                break

            await asyncio.sleep(2)

        if yeni_sarki:

            queue.append(
                yeni_sarki
            )

            print(
                f"[RADYO] Yeni şarkı: "
                f"{yeni_sarki.get('title', 'Bilinmiyor')}"
            )

        else:

            print(
                "[RADYO] Şarkı bulunamadı."
            )

            print(
                "[RADYO] Bot ses kanalında kalacak."
            )

            await muzik_panel_guncelle(
                guild
            )

            # 5 saniye bekle, sonra tekrar dene
            await asyncio.sleep(5)

            if (
                otomatik_muzik.get(
                    guild_id,
                    False
                )
                and guild.voice_client
                and guild.voice_client.is_connected()
            ):

                await sonraki_sarki(
                    guild
                )

            return

    # --------------------------------------------------------
    # KUYRUK HALA BOŞ
    # --------------------------------------------------------

    if not queue:

        if not otomatik_muzik.get(
            guild_id,
            False
        ):

            voice = guild.voice_client

            if voice:

                try:
                    await voice.disconnect()

                except Exception:
                    pass

            await muzik_panel_guncelle(
                guild
            )

        return

    voice = guild.voice_client

    if not voice or not voice.is_connected():
        return

    settings = get_settings(
        guild_id
    )

    current = queue[0]

    # --------------------------------------------------------
    # YOUTUBE SES URL
    # --------------------------------------------------------

    try:

        # yt-dlp ağ işlemi senkrondur; doğrudan async fonksiyonda
        # çalıştırılırsa Discord event loop'unu bloke edip
        # slash komutlarının 3 saniyelik yanıt süresini aşabilir.
        audio_url = await asyncio.to_thread(
            ses_urlini_al,
            current["webpage_url"]
        )

    except Exception as e:

        print(
            "SES URL HATASI:",
            e
        )

        if queue:
            queue.pop(0)

        await asyncio.sleep(1)

        await sonraki_sarki(
            guild
        )

        return

    if not audio_url:

        print(
            f"[MÜZİK] Ses URL alınamadı: "
            f"{current.get('title', 'Bilinmiyor')}"
        )

        if queue:
            queue.pop(0)

        await asyncio.sleep(1)

        await sonraki_sarki(
            guild
        )

        return

    # --------------------------------------------------------
    # FFMPEG
    # --------------------------------------------------------

    if not FFMPEG_PATH:

        print(
            "FFMPEG BULUNAMADI!"
        )

        return

    try:

        source = discord.FFmpegPCMAudio(
            audio_url,
            executable=FFMPEG_PATH,
            **FFMPEG_OPTIONS
        )

        volume_source = (
            discord.PCMVolumeTransformer(
                source,
                volume=settings["volume"]
            )
        )

        def after_play(error):

            if error:

                print(
                    "OYUN HATASI:",
                    error
                )

            try:

                asyncio.run_coroutine_threadsafe(
                    muzik_bitti(guild),
                    bot.loop
                )

            except Exception as e:

                print(
                    "SONRAKİ ŞARKI CALLBACK HATASI:",
                    e
                )

        voice.play(
            volume_source,
            after=after_play
        )

        print(
            f"[MÜZİK] Şimdi çalıyor: "
            f"{current.get('title', 'Bilinmeyen Şarkı')}"
        )

        await muzik_panel_guncelle(
            guild
        )

    except Exception as e:

        print(
            "FFMPEG OYNATMA HATASI:",
            e
        )


# ============================================================
# ŞARKI BİTTİ
# ============================================================

async def muzik_bitti(guild):

    guild_id = guild.id

    queue = get_queue(
        guild_id
    )

    if not queue:
        return

    settings = get_settings(
        guild_id
    )

    # --------------------------------------------------------
    # LOOP
    # --------------------------------------------------------

    if settings["loop"]:

        await asyncio.sleep(
            0.5
        )

        await sonraki_sarki(
            guild
        )

        return

    # --------------------------------------------------------
    # BİTEN ŞARKI
    # --------------------------------------------------------

    biten = queue.pop(
        0
    )

    print(
        f"[MÜZİK BİTTİ] "
        f"{biten.get('title', 'Bilinmeyen Şarkı')}"
    )

    # --------------------------------------------------------
    # KUYRUK BOŞSA RADYO DEVAM ETSİN
    # --------------------------------------------------------

    if not queue:

        if otomatik_muzik.get(
            guild_id,
            False
        ):

            print(
                "[RADYO] Kuyruk boşaldı."
            )

            print(
                "[RADYO] Yeni rastgele şarkı aranıyor..."
            )

            await asyncio.sleep(
                1
            )

            await sonraki_sarki(
                guild
            )

            return

        # ----------------------------------------------------
        # OTOMATİK KAPALIYSA ÇIK
        # ----------------------------------------------------

        voice = guild.voice_client

        if voice:

            try:
                await voice.disconnect()

            except Exception:
                pass

        await muzik_panel_guncelle(
            guild
        )

        return

    # --------------------------------------------------------
    # NORMAL KUYRUK
    # --------------------------------------------------------

    await asyncio.sleep(
        0.5
    )

    await sonraki_sarki(
        guild
    )


# ============================================================
# MÜZİK PANELİ
# ============================================================

class MuzikPanel(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Önceki",
        emoji="⏮️",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_previous"
    )
    async def previous(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if not guild:
            return

        queue = get_queue(
            guild.id
        )

        if len(queue) < 2:

            await interaction.response.send_message(
                "❌ Önceki şarkı yok.",
                ephemeral=True
            )

            return

        current = queue.pop(0)

        queue.append(current)

        voice = guild.voice_client

        if voice:

            if (
                voice.is_playing()
                or voice.is_paused()
            ):

                voice.stop()

            else:

                await sonraki_sarki(
                    guild
                )

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


    @discord.ui.button(
        label="Oynat / Duraklat",
        emoji="⏯️",
        style=discord.ButtonStyle.primary,
        custom_id="veloria_music_pause"
    )
    async def pause_resume(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if not guild:
            return

        voice = guild.voice_client

        if not voice:

            await interaction.response.send_message(
                "❌ Bot ses kanalında değil.",
                ephemeral=True
            )

            return

        if voice.is_playing():

            voice.pause()

            await interaction.response.edit_message(
                embed=muzik_embed(guild),
                view=MuzikPanel()
            )

        elif voice.is_paused():

            voice.resume()

            await interaction.response.edit_message(
                embed=muzik_embed(guild),
                view=MuzikPanel()
            )

        else:

            await interaction.response.send_message(
                "❌ Şu anda çalan şarkı yok.",
                ephemeral=True
            )


    @discord.ui.button(
        label="Sonraki",
        emoji="⏭️",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_skip"
    )
    async def skip(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if not guild:
            return

        voice = guild.voice_client

        if not voice:

            await interaction.response.send_message(
                "❌ Bot ses kanalında değil.",
                ephemeral=True
            )

            return

        if not (
            voice.is_playing()
            or voice.is_paused()
        ):

            await interaction.response.send_message(
                "❌ Çalan şarkı yok.",
                ephemeral=True
            )

            return

        await interaction.response.defer()

        voice.stop()


    @discord.ui.button(
        label="Karıştır",
        emoji="🔀",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_shuffle"
    )
    async def shuffle(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        queue = get_queue(
            guild.id
        )

        if len(queue) <= 2:

            await interaction.response.send_message(
                "❌ Kuyrukta karıştırılacak yeterli şarkı yok.",
                ephemeral=True
            )

            return

        current = queue[0]

        kalan = queue[1:]

        random.shuffle(
            kalan
        )

        muzik_kuyruklari[
            guild.id
        ] = [current] + kalan

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


    @discord.ui.button(
        label="Döngü",
        emoji="🔁",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_loop"
    )
    async def loop(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        settings = get_settings(
            guild.id
        )

        settings["loop"] = not settings["loop"]

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


    @discord.ui.button(
        label="Kuyruk",
        emoji="📋",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_queue"
    )
    async def queue_button(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        queue = get_queue(
            guild.id
        )

        if not queue:

            await interaction.response.send_message(
                "📭 Kuyruk boş.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title=f"📋 {BOT_NAME} • KUYRUK",
            color=PURPLE
        )

        liste = []

        for i, song in enumerate(
            queue[:15]
        ):

            if i == 0:

                liste.append(
                    f"🎧 **Şimdi:** "
                    f"{song['title']}"
                )

            else:

                liste.append(
                    f"`{i}.` "
                    f"{song['title']}"
                )

        embed.description = "\n".join(
            liste
        )

        if len(queue) > 15:

            embed.description += (
                f"\n\n... ve "
                f"{len(queue) - 15} şarkı daha."
            )

        embed.set_footer(
            text=f"Toplam {len(queue)} şarkı"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


    @discord.ui.button(
        label="Ses -",
        emoji="🔉",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_volume_down"
    )
    async def volume_down(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        settings = get_settings(
            guild.id
        )

        yeni_ses = round(
            settings["volume"] - 0.10,
            2
        )

        yeni_ses = max(
            0.0,
            yeni_ses
        )

        settings["volume"] = yeni_ses

        voice = guild.voice_client

        if voice and voice.source:

            try:

                if isinstance(
                    voice.source,
                    discord.PCMVolumeTransformer
                ):

                    voice.source.volume = yeni_ses

            except Exception:
                pass

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


    @discord.ui.button(
        label="Ses +",
        emoji="🔊",
        style=discord.ButtonStyle.secondary,
        custom_id="veloria_music_volume_up"
    )
    async def volume_up(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        settings = get_settings(
            guild.id
        )

        yeni_ses = round(
            settings["volume"] + 0.10,
            2
        )

        yeni_ses = min(
            1.0,
            yeni_ses
        )

        settings["volume"] = yeni_ses

        voice = guild.voice_client

        if voice and voice.source:

            try:

                if isinstance(
                    voice.source,
                    discord.PCMVolumeTransformer
                ):

                    voice.source.volume = yeni_ses

            except Exception:
                pass

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


    @discord.ui.button(
        label="Durdur",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="veloria_music_stop"
    )
    async def stop(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        otomatik_muzik[guild.id] = False

        radio_dil.pop(
            guild.id,
            None
        )

        radio_gecmisi.pop(
            guild.id,
            None
        )

        queue = get_queue(
            guild.id
        )

        queue.clear()

        voice = guild.voice_client

        if voice:

            try:
                voice.stop()

            except Exception:
                pass

            try:
                await voice.disconnect()

            except Exception:
                pass

        await interaction.response.edit_message(
            embed=muzik_embed(guild),
            view=MuzikPanel()
        )


# ============================================================
# /PLAY
# ============================================================

@bot.tree.command(
    name="play",
    description="YouTube'dan müzik çalar."
)
@app_commands.describe(
    arama="Şarkı adı veya YouTube linki"
)
async def play(
    interaction: discord.Interaction,
    arama: str
):

    if not interaction.guild:

        await interaction.response.send_message(
            "❌ Bu komut sadece sunucuda kullanılabilir.",
            ephemeral=True
        )

        return

    if not interaction.user.voice:

        await interaction.response.send_message(
            "❌ Önce bir ses kanalına gir.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    guild = interaction.guild

    kanal = interaction.user.voice.channel

    voice = guild.voice_client

    try:

        if voice:

            if voice.channel != kanal:

                await voice.move_to(
                    kanal
                )

        else:

            voice = await kanal.connect()

    except Exception as e:

        await interaction.followup.send(
            f"❌ Ses kanalına bağlanamadım:\n`{e}`"
        )

        return

    song = await asyncio.to_thread(
        muzik_ara,
        arama
    )

    if not song:

        await interaction.followup.send(
            "❌ Şarkı bulunamadı."
        )

        return

    queue = get_queue(
        guild.id
    )

    ilk_sarki = len(queue) == 0

    queue.append(song)

    if ilk_sarki:

        otomatik_muzik[guild.id] = True

        if turkce_mi(
            arama,
            song
        ):

            radio_dil[guild.id] = "turkce"

        else:

            radio_dil[guild.id] = "yabanci"

        radio_gecmisi[guild.id] = [
            song.get(
                "webpage_url",
                ""
            )
        ]

    if (
        not voice.is_playing()
        and not voice.is_paused()
    ):

        await sonraki_sarki(
            guild
        )

    await interaction.followup.send(
        embed=muzik_embed(guild),
        view=MuzikPanel()
    )

    try:

        message = await interaction.original_response()

        muzik_panelleri[
            guild.id
        ] = message

    except Exception:
        pass


# ============================================================
# /MÜZİK
# ============================================================

@bot.tree.command(
    name="müzik",
    description="Müzik panelini açar."
)
async def muzik(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    await interaction.response.send_message(
        embed=muzik_embed(
            interaction.guild
        ),
        view=MuzikPanel()
    )

    try:

        message = await interaction.original_response()

        muzik_panelleri[
            interaction.guild.id
        ] = message

    except Exception:
        pass


# ============================================================
# MÜZİK KOMUTLARI
# ============================================================

@bot.tree.command(
    name="skip",
    description="Mevcut şarkıyı geçer."
)
async def skip_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    voice = interaction.guild.voice_client

    if not voice:

        await interaction.response.send_message(
            "❌ Bot ses kanalında değil.",
            ephemeral=True
        )

        return

    if not (
        voice.is_playing()
        or voice.is_paused()
    ):

        await interaction.response.send_message(
            "❌ Çalan şarkı yok.",
            ephemeral=True
        )

        return

    voice.stop()

    await interaction.response.send_message(
        "⏭️ Şarkı geçildi."
    )


@bot.tree.command(
    name="pause",
    description="Müziği duraklatır."
)
async def pause_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    voice = interaction.guild.voice_client

    if not voice or not voice.is_playing():

        await interaction.response.send_message(
            "❌ Çalan şarkı yok.",
            ephemeral=True
        )

        return

    voice.pause()

    await interaction.response.send_message(
        "⏸️ Müzik duraklatıldı."
    )

    await muzik_panel_guncelle(
        interaction.guild
    )


@bot.tree.command(
    name="resume",
    description="Müziği devam ettirir."
)
async def resume_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    voice = interaction.guild.voice_client

    if not voice or not voice.is_paused():

        await interaction.response.send_message(
            "❌ Müzik duraklatılmış değil.",
            ephemeral=True
        )

        return

    voice.resume()

    await interaction.response.send_message(
        "▶️ Müzik devam ediyor."
    )

    await muzik_panel_guncelle(
        interaction.guild
    )


@bot.tree.command(
    name="stop",
    description="Müziği tamamen durdurur."
)
async def stop_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    guild = interaction.guild

    otomatik_muzik[guild.id] = False

    radio_dil.pop(
        guild.id,
        None
    )

    radio_gecmisi.pop(
        guild.id,
        None
    )

    get_queue(
        guild.id
    ).clear()

    voice = guild.voice_client

    if voice:

        try:
            voice.stop()

        except Exception:
            pass

        try:
            await voice.disconnect()

        except Exception:
            pass

    await interaction.response.send_message(
        "⏹️ Müzik durduruldu ve kuyruk temizlendi."
    )

    await muzik_panel_guncelle(
        guild
    )


@bot.tree.command(
    name="kuyruk",
    description="Müzik kuyruğunu gösterir."
)
async def kuyruk_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    queue = get_queue(
        interaction.guild.id
    )

    if not queue:

        await interaction.response.send_message(
            "📭 Kuyruk boş.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=f"📋 {BOT_NAME} • MUSIC QUEUE",
        color=PURPLE
    )

    liste = []

    for i, song in enumerate(
        queue[:15]
    ):

        if i == 0:

            liste.append(
                f"🎧 **Şimdi:** "
                f"{song['title']}"
            )

        else:

            liste.append(
                f"`{i}.` "
                f"{song['title']}"
            )

    embed.description = "\n".join(
        liste
    )

    embed.set_footer(
        text=f"Toplam {len(queue)} şarkı"
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="shuffle",
    description="Kuyruğu karıştırır."
)
async def shuffle_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    queue = get_queue(
        interaction.guild.id
    )

    if len(queue) <= 2:

        await interaction.response.send_message(
            "❌ Kuyrukta yeterli şarkı yok.",
            ephemeral=True
        )

        return

    current = queue[0]

    kalan = queue[1:]

    random.shuffle(
        kalan
    )

    muzik_kuyruklari[
        interaction.guild.id
    ] = [current] + kalan

    await interaction.response.send_message(
        "🔀 Kuyruk karıştırıldı."
    )

    await muzik_panel_guncelle(
        interaction.guild
    )


@bot.tree.command(
    name="loop",
    description="Şarkı döngüsünü açar veya kapatır."
)
async def loop_command(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    settings = get_settings(
        interaction.guild.id
    )

    settings["loop"] = not settings["loop"]

    if settings["loop"]:
        mesaj = "🔁 Döngü açıldı."

    else:
        mesaj = "⏹️ Döngü kapatıldı."

    await interaction.response.send_message(
        mesaj
    )

    await muzik_panel_guncelle(
        interaction.guild
    )


@bot.tree.command(
    name="ses",
    description="Müzik sesini ayarlar."
)
@app_commands.describe(
    seviye="0 ile 100 arasında ses"
)
async def ses_command(
    interaction: discord.Interaction,
    seviye: app_commands.Range[int, 0, 100]
):

    if not interaction.guild:
        return

    settings = get_settings(
        interaction.guild.id
    )

    yeni_ses = seviye / 100

    settings["volume"] = yeni_ses

    voice = interaction.guild.voice_client

    if voice and voice.source:

        try:

            if isinstance(
                voice.source,
                discord.PCMVolumeTransformer
            ):

                voice.source.volume = yeni_ses

        except Exception:
            pass

    await interaction.response.send_message(
        f"🔊 Ses seviyesi `%{seviye}` olarak ayarlandı."
    )

    await muzik_panel_guncelle(
        interaction.guild
    )


# ============================================================
# EK MÜZİK
# ============================================================

@bot.tree.command(
    name="join",
    description="Botu ses kanalına sokar."
)
async def join(
    interaction: discord.Interaction
):

    if not interaction.user.voice:

        await interaction.response.send_message(
            "❌ Önce ses kanalına gir.",
            ephemeral=True
        )

        return

    kanal = interaction.user.voice.channel

    try:

        if interaction.guild.voice_client:

            await interaction.guild.voice_client.move_to(
                kanal
            )

        else:

            await kanal.connect()

        await interaction.response.send_message(
            f"🔊 {kanal.mention} kanalına girdim."
        )

    except Exception as e:

        await interaction.response.send_message(
            f"❌ Bağlanamadım: `{e}`",
            ephemeral=True
        )


@bot.tree.command(
    name="leave",
    description="Botu ses kanalından çıkarır."
)
async def leave(
    interaction: discord.Interaction
):

    voice = interaction.guild.voice_client

    if not voice:

        await interaction.response.send_message(
            "❌ Bot zaten ses kanalında değil.",
            ephemeral=True
        )

        return

    get_queue(
        interaction.guild.id
    ).clear()

    otomatik_muzik[
        interaction.guild.id
    ] = False

    await voice.disconnect()

    await interaction.response.send_message(
        "👋 Ses kanalından çıktım."
    )


@bot.tree.command(
    name="clearqueue",
    description="Müzik kuyruğunu temizler."
)
async def clearqueue(
    interaction: discord.Interaction
):

    queue = get_queue(
        interaction.guild.id
    )

    if len(queue) <= 1:

        await interaction.response.send_message(
            "📭 Kuyrukta temizlenecek şarkı yok.",
            ephemeral=True
        )

        return

    current = queue[0]

    muzik_kuyruklari[
        interaction.guild.id
    ] = [current]

    await interaction.response.send_message(
        "🧹 Kuyruk temizlendi."
    )


@bot.tree.command(
    name="nowplaying",
    description="Şu anda çalan şarkıyı gösterir."
)
async def nowplaying(
    interaction: discord.Interaction
):

    if not interaction.guild:
        return

    queue = get_queue(
        interaction.guild.id
    )

    if not queue:

        await interaction.response.send_message(
            "🎵 Şu anda müzik çalmıyor.",
            ephemeral=True
        )

        return

    song = queue[0]

    embed = discord.Embed(
        title="🎧 Şimdi Çalıyor",
        description=(
            f"**{song['title']}**\n"
            f"👤 {song.get('uploader', 'Bilinmiyor')}\n"
            f"⏱️ {format_duration(song.get('duration'))}"
        ),
        color=PURPLE
    )

    if song.get("thumbnail"):

        embed.set_thumbnail(
            url=song["thumbnail"]
        )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="remove",
    description="Kuyruktan şarkı siler."
)
@app_commands.describe(
    sıra="Kuyruktaki şarkı numarası"
)
async def remove(
    interaction: discord.Interaction,
    sıra: app_commands.Range[int, 1, 100]
):

    queue = get_queue(
        interaction.guild.id
    )

    index = sıra

    if index >= len(queue):

        await interaction.response.send_message(
            "❌ Böyle bir sıra yok.",
            ephemeral=True
        )

        return

    song = queue.pop(index)

    await interaction.response.send_message(
        f"🗑️ Kuyruktan çıkarıldı: **{song['title']}**"
    )


# ============================================================
# MODERASYON
# ============================================================

@bot.tree.command(
    name="sil",
    description="Mesajları siler."
)
@app_commands.describe(
    miktar="Silinecek mesaj sayısı"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def sil(
    interaction: discord.Interaction,
    miktar: app_commands.Range[int, 1, 100]
):

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=miktar
    )

    await interaction.followup.send(
        f"🗑️ `{len(deleted)}` mesaj silindi.",
        ephemeral=True
    )


@bot.tree.command(
    name="purge",
    description="Mesajları temizler."
)
@app_commands.describe(
    miktar="Mesaj sayısı"
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def purge(
    interaction: discord.Interaction,
    miktar: app_commands.Range[int, 1, 100]
):

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=miktar
    )

    await interaction.followup.send(
        f"🧹 `{len(deleted)}` mesaj temizlendi.",
        ephemeral=True
    )


@bot.tree.command(
    name="kick",
    description="Kullanıcıyı sunucudan atar."
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick(
    interaction: discord.Interaction,
    uye: discord.Member,
    sebep: str = "Sebep belirtilmedi."
):

    if uye == interaction.user:

        await interaction.response.send_message(
            "❌ Kendini atamazsın.",
            ephemeral=True
        )

        return

    if uye.top_role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu kullanıcının rolü benden yüksek veya eşit.",
            ephemeral=True
        )

        return

    try:

        await uye.kick(
            reason=sebep
        )

        await interaction.response.send_message(
            f"👢 {uye.mention} sunucudan atıldı.\n"
            f"**Sebep:** {sebep}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Bu kullanıcıyı atamıyorum.",
            ephemeral=True
        )


@bot.tree.command(
    name="ban",
    description="Kullanıcıyı banlar."
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban(
    interaction: discord.Interaction,
    uye: discord.Member,
    sebep: str = "Sebep belirtilmedi."
):

    if uye == interaction.user:

        await interaction.response.send_message(
            "❌ Kendini banlayamazsın.",
            ephemeral=True
        )

        return

    if uye.top_role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu kullanıcının rolü benden yüksek veya eşit.",
            ephemeral=True
        )

        return

    try:

        await uye.ban(
            reason=sebep
        )

        await interaction.response.send_message(
            f"🔨 {uye.mention} yasaklandı.\n"
            f"**Sebep:** {sebep}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Bu kullanıcıyı banlayamıyorum.",
            ephemeral=True
        )


@bot.tree.command(
    name="unban",
    description="Ban kaldırır."
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def unban(
    interaction: discord.Interaction,
    kullanici_id: str
):

    try:

        user = await bot.fetch_user(
            int(kullanici_id)
        )

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            f"🔓 `{user}` kullanıcısının banı kaldırıldı."
        )

    except ValueError:

        await interaction.response.send_message(
            "❌ Geçerli bir kullanıcı ID'si gir.",
            ephemeral=True
        )

    except discord.NotFound:

        await interaction.response.send_message(
            "❌ Kullanıcı banlı değil.",
            ephemeral=True
        )


@bot.tree.command(
    name="timeout",
    description="Kullanıcıya timeout verir."
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def timeout(
    interaction: discord.Interaction,
    uye: discord.Member,
    dakika: app_commands.Range[int, 1, 40320],
    sebep: str = "Sebep belirtilmedi."
):

    if uye.top_role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu kullanıcıya timeout veremiyorum.",
            ephemeral=True
        )

        return

    try:

        await uye.timeout(
            timedelta(
                minutes=dakika
            ),
            reason=sebep
        )

        await interaction.response.send_message(
            f"⏳ {uye.mention} "
            f"`{dakika}` dakika timeout aldı.\n"
            f"**Sebep:** {sebep}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Timeout veremiyorum.",
            ephemeral=True
        )


@bot.tree.command(
    name="untimeout",
    description="Timeout kaldırır."
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def untimeout(
    interaction: discord.Interaction,
    uye: discord.Member
):

    try:

        await uye.timeout(None)

        await interaction.response.send_message(
            f"🔓 {uye.mention} timeouttan çıkarıldı."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Timeout kaldırılamadı.",
            ephemeral=True
        )


@bot.tree.command(
    name="slowmode",
    description="Slowmode ayarlar."
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def slowmode(
    interaction: discord.Interaction,
    saniye: app_commands.Range[int, 0, 21600]
):

    await interaction.channel.edit(
        slowmode_delay=saniye
    )

    await interaction.response.send_message(
        f"🐌 Slowmode `{saniye}` saniye olarak ayarlandı."
    )


@bot.tree.command(
    name="lock",
    description="Kanalı kilitler."
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def lock(
    interaction: discord.Interaction
):

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔒 Kanal kilitlendi."
    )


@bot.tree.command(
    name="unlock",
    description="Kanalın kilidini açar."
)
@app_commands.checks.has_permissions(
    manage_channels=True
)
async def unlock(
    interaction: discord.Interaction
):

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔓 Kanal kilidi açıldı."
    )


@bot.tree.command(
    name="nick",
    description="Kullanıcının takma adını değiştirir."
)
@app_commands.checks.has_permissions(
    manage_nicknames=True
)
async def nick(
    interaction: discord.Interaction,
    uye: discord.Member,
    isim: str
):

    try:

        await uye.edit(
            nick=isim
        )

        await interaction.response.send_message(
            f"✅ {uye.mention} takma adı `{isim}` yapıldı."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Takma adını değiştiremiyorum.",
            ephemeral=True
        )


@bot.tree.command(
    name="rolver",
    description="Kullanıcıya rol verir."
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def rolover(
    interaction: discord.Interaction,
    uye: discord.Member,
    rol: discord.Role
):

    if rol >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu rol benim en yüksek rolümden yukarıda.",
            ephemeral=True
        )

        return

    try:

        await uye.add_roles(
            rol
        )

        await interaction.response.send_message(
            f"✅ {uye.mention} kullanıcısına "
            f"{rol.mention} verildi."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Bu rolü veremiyorum.",
            ephemeral=True
        )


@bot.tree.command(
    name="rolal",
    description="Kullanıcıdan rol alır."
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def rolar(
    interaction: discord.Interaction,
    uye: discord.Member,
    rol: discord.Role
):

    if rol >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu rolü yönetemiyorum.",
            ephemeral=True
        )

        return

    try:

        await uye.remove_roles(
            rol
        )

        await interaction.response.send_message(
            f"✅ {uye.mention} kullanıcısından "
            f"{rol.mention} alındı."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ Bu rolü alamıyorum.",
            ephemeral=True
        )


# ============================================================
# WARN SİSTEMİ
# ============================================================

@bot.tree.command(
    name="warn",
    description="Kullanıcıya uyarı verir."
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def warn(
    interaction: discord.Interaction,
    uye: discord.Member,
    sebep: str = "Sebep belirtilmedi."
):

    db_execute(
        """
        INSERT INTO warnings
        (guild_id, user_id, moderator_id, reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            uye.id,
            interaction.user.id,
            sebep,
            int(time.time())
        )
    )

    await interaction.response.send_message(
        f"⚠️ {uye.mention} uyarıldı.\n"
        f"**Sebep:** {sebep}"
    )


@bot.tree.command(
    name="warnings",
    description="Kullanıcının uyarılarını gösterir."
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def warnings(
    interaction: discord.Interaction,
    uye: discord.Member
):

    rows = db_execute(
        """
        SELECT reason, moderator_id, created_at
        FROM warnings
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (
            interaction.guild.id,
            uye.id
        ),
        commit=False
    ).fetchall()

    if not rows:

        await interaction.response.send_message(
            "✅ Bu kullanıcının uyarısı yok.",
            ephemeral=True
        )

        return

    lines = []

    for i, row in enumerate(
        rows,
        1
    ):

        reason, moderator, created_at = row

        lines.append(
            f"**{i}.** {reason}\n"
            f"👮 <@{moderator}> • "
            f"<t:{created_at}:R>"
        )

    embed = discord.Embed(
        title=f"⚠️ {uye} Uyarıları",
        description="\n\n".join(lines),
        color=PURPLE
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="clearwarnings",
    description="Kullanıcının uyarılarını siler."
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def clearwarnings(
    interaction: discord.Interaction,
    uye: discord.Member
):

    db_execute(
        """
        DELETE FROM warnings
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            interaction.guild.id,
            uye.id
        )
    )

    await interaction.response.send_message(
        f"🧹 {uye.mention} uyarıları temizlendi."
    )


# ============================================================
# BİLGİ
# ============================================================

@bot.tree.command(
    name="avatar",
    description="Avatar gösterir."
)
async def avatar(
    interaction: discord.Interaction,
    uye: discord.Member = None
):

    uye = uye or interaction.user

    embed = discord.Embed(
        title=f"🖼️ {uye.display_name} Avatarı",
        color=PURPLE
    )

    embed.set_image(
        url=uye.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="banner",
    description="Kullanıcı bannerını gösterir."
)
async def banner(
    interaction: discord.Interaction,
    uye: discord.User = None
):

    uye = uye or interaction.user

    try:

        user = await bot.fetch_user(
            uye.id
        )

        if not user.banner:

            await interaction.response.send_message(
                "❌ Bu kullanıcının bannerı yok.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title=f"🖼️ {user} Banner",
            color=PURPLE
        )

        embed.set_image(
            url=user.banner.url
        )

        await interaction.response.send_message(
            embed=embed
        )

    except Exception:

        await interaction.response.send_message(
            "❌ Banner alınamadı.",
            ephemeral=True
        )


@bot.tree.command(
    name="kullanıcıbilgi",
    description="Kullanıcı bilgilerini gösterir."
)
async def kullanicibilgi(
    interaction: discord.Interaction,
    uye: discord.Member = None
):

    uye = uye or interaction.user

    embed = discord.Embed(
        title="👤 Kullanıcı Bilgileri",
        color=PURPLE
    )

    embed.set_thumbnail(
        url=uye.display_avatar.url
    )

    embed.add_field(
        name="Kullanıcı",
        value=uye.mention,
        inline=False
    )

    embed.add_field(
        name="ID",
        value=f"`{uye.id}`",
        inline=True
    )

    embed.add_field(
        name="Hesap",
        value=discord.utils.format_dt(
            uye.created_at,
            "R"
        ),
        inline=True
    )

    if uye.joined_at:

        embed.add_field(
            name="Sunucuya Katılım",
            value=discord.utils.format_dt(
                uye.joined_at,
                "R"
            ),
            inline=True
        )

    roller = [
        role.mention
        for role in uye.roles[1:]
    ]

    embed.add_field(
        name="Roller",
        value=(
            " ".join(roller[:15])
            if roller
            else "Rol yok."
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="sunucubilgi",
    description="Sunucu bilgilerini gösterir."
)
async def sunucubilgi(
    interaction: discord.Interaction
):

    guild = interaction.guild

    embed = discord.Embed(
        title=f"🏰 {guild.name}",
        color=PURPLE
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    embed.add_field(
        name="👥 Üyeler",
        value=f"`{guild.member_count}`",
        inline=True
    )

    embed.add_field(
        name="📁 Kanallar",
        value=f"`{len(guild.channels)}`",
        inline=True
    )

    embed.add_field(
        name="🎭 Roller",
        value=f"`{len(guild.roles)}`",
        inline=True
    )

    embed.add_field(
        name="🆔 Sunucu ID",
        value=f"`{guild.id}`",
        inline=True
    )

    embed.add_field(
        name="👑 Sahip",
        value=f"<@{guild.owner_id}>",
        inline=True
    )

    embed.add_field(
        name="📅 Oluşturulma",
        value=discord.utils.format_dt(
            guild.created_at,
            "D"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="roleinfo",
    description="Rol bilgilerini gösterir."
)
async def roleinfo(
    interaction: discord.Interaction,
    rol: discord.Role
):

    embed = discord.Embed(
        title=f"🎭 {rol.name}",
        color=rol.color if rol.color.value else PURPLE
    )

    embed.add_field(
        name="ID",
        value=f"`{rol.id}`",
        inline=True
    )

    embed.add_field(
        name="Pozisyon",
        value=f"`{rol.position}`",
        inline=True
    )

    embed.add_field(
        name="Üye Sayısı",
        value=f"`{len(rol.members)}`",
        inline=True
    )

    embed.add_field(
        name="Mentionable",
        value=str(rol.mentionable),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# EKONOMİ
# ============================================================

@bot.tree.command(
    name="bakiye",
    description="Bakiyeni gösterir."
)
async def bakiye(
    interaction: discord.Interaction,
    uye: discord.Member = None
):

    uye = uye or interaction.user

    miktar = get_balance(
        uye.id
    )

    embed = discord.Embed(
        title="💰 Bakiye",
        description=(
            f"{uye.mention}\n\n"
            f"💵 **{miktar:,} TL**"
        ),
        color=PURPLE
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="günlük",
    description="Günlük para ödülü al."
)
async def gunluk(
    interaction: discord.Interaction
):

    odul = random.randint(
        100,
        500
    )

    yeni = add_balance(
        interaction.user.id,
        odul
    )

    await interaction.response.send_message(
        f"🎁 Günlük ödülün: **{odul:,} TL**\n"
        f"💰 Yeni bakiyen: **{yeni:,} TL**"
    )


@bot.tree.command(
    name="weekly",
    description="Haftalık para ödülü al."
)
async def weekly(
    interaction: discord.Interaction
):

    odul = random.randint(
        1000,
        5000
    )

    yeni = add_balance(
        interaction.user.id,
        odul
    )

    await interaction.response.send_message(
        f"🎁 Haftalık ödülün: **{odul:,} TL**\n"
        f"💰 Yeni bakiyen: **{yeni:,} TL**"
    )


@bot.tree.command(
    name="work",
    description="Çalışıp para kazan."
)
async def work(
    interaction: discord.Interaction
):

    jobs = [
        "oto tamircisi",
        "garson",
        "kurye",
        "madenci",
        "yazılımcı",
        "grafiker",
        "kasiyer"
    ]

    job = random.choice(
        jobs
    )

    kazanc = random.randint(
        100,
        750
    )

    yeni = add_balance(
        interaction.user.id,
        kazanc
    )

    await interaction.response.send_message(
        f"🛠️ Bugün **{job}** olarak çalıştın.\n"
        f"💵 Kazanç: **{kazanc:,} TL**\n"
        f"💰 Bakiye: **{yeni:,} TL**"
    )


@bot.tree.command(
    name="give",
    description="Başka kullanıcıya para gönderir."
)
async def give(
    interaction: discord.Interaction,
    uye: discord.Member,
    miktar: app_commands.Range[int, 1, 1_000_000]
):

    if uye == interaction.user:

        await interaction.response.send_message(
            "❌ Kendine para gönderemezsin.",
            ephemeral=True
        )

        return

    bakiye = get_balance(
        interaction.user.id
    )

    if bakiye < miktar:

        await interaction.response.send_message(
            "❌ Yeterli paran yok.",
            ephemeral=True
        )

        return

    add_balance(
        interaction.user.id,
        -miktar
    )

    add_balance(
        uye.id,
        miktar
    )

    await interaction.response.send_message(
        f"💸 {uye.mention} kullanıcısına "
        f"**{miktar:,} TL** gönderildi."
    )


@bot.tree.command(
    name="leaderboard",
    description="En zengin kullanıcıları gösterir."
)
async def leaderboard(
    interaction: discord.Interaction
):

    rows = db_execute(
        """
        SELECT user_id, money
        FROM balances
        ORDER BY money DESC
        LIMIT 10
        """,
        commit=False
    ).fetchall()

    if not rows:

        await interaction.response.send_message(
            "📭 Henüz ekonomi verisi yok."
        )

        return

    lines = []

    for i, row in enumerate(
        rows,
        1
    ):

        user_id, money = row

        lines.append(
            f"**{i}.** <@{user_id}> "
            f"— **{money:,} TL**"
        )

    embed = discord.Embed(
        title="💰 En Zenginler",
        description="\n".join(lines),
        color=PURPLE
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# XP
# ============================================================

@bot.tree.command(
    name="seviye",
    description="XP ve seviyeni gösterir."
)
async def seviye(
    interaction: discord.Interaction,
    uye: discord.Member = None
):

    uye = uye or interaction.user

    data = get_xp(
        uye.id
    )

    gereken = data["level"] * 100

    embed = discord.Embed(
        title="⭐ Seviye",
        color=PURPLE
    )

    embed.set_thumbnail(
        url=uye.display_avatar.url
    )

    embed.description = (
        f"## {uye.display_name}\n\n"
        f"🏆 **Seviye:** `{data['level']}`\n"
        f"✨ **XP:** "
        f"`{data['xp']} / {gereken}`"
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="rank",
    description="Seviye sıralamasını gösterir."
)
async def rank(
    interaction: discord.Interaction
):

    rows = db_execute(
        """
        SELECT user_id, level, xp
        FROM xp
        ORDER BY level DESC, xp DESC
        LIMIT 10
        """,
        commit=False
    ).fetchall()

    if not rows:

        await interaction.response.send_message(
            "📭 Henüz XP verisi yok."
        )

        return

    lines = []

    for i, row in enumerate(
        rows,
        1
    ):

        user_id, level, xp = row

        lines.append(
            f"**{i}.** <@{user_id}> "
            f"— Seviye **{level}** "
            f"(`{xp} XP`)"
        )

    embed = discord.Embed(
        title="🏆 XP Sıralaması",
        description="\n".join(lines),
        color=PURPLE
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# EĞLENCE
# ============================================================

@bot.tree.command(
    name="coinflip",
    description="Yazı tura atar."
)
async def coinflip(
    interaction: discord.Interaction
):

    sonuc = random.choice(
        [
            "🪙 Yazı",
            "🪙 Tura"
        ]
    )

    await interaction.response.send_message(
        f"**{sonuc}**"
    )


@bot.tree.command(
    name="dice",
    description="Zar atar."
)
async def dice(
    interaction: discord.Interaction,
    taraf: app_commands.Range[int, 2, 100]
):

    sonuc = random.randint(
        1,
        taraf
    )

    await interaction.response.send_message(
        f"🎲 Zar sonucu: **{sonuc}** / `{taraf}`"
    )


@bot.tree.command(
    name="8ball",
    description="Sihirli 8 topuna soru sor."
)
async def eightball(
    interaction: discord.Interaction,
    soru: str
):

    cevaplar = [
        "Evet.",
        "Hayır.",
        "Büyük ihtimalle.",
        "Sanmıyorum.",
        "Kesinlikle.",
        "Şimdilik belli değil.",
        "Bence dene.",
        "Hiç sanmıyorum."
    ]

    await interaction.response.send_message(
        f"🎱 **Soru:** {soru}\n"
        f"🔮 **Cevap:** {random.choice(cevaplar)}"
    )


@bot.tree.command(
    name="choose",
    description="Seçeneklerden birini seçer."
)
async def choose(
    interaction: discord.Interaction,
    secenekler: str
):

    secenekler_liste = [
        x.strip()
        for x in secenekler.split(",")
        if x.strip()
    ]

    if len(secenekler_liste) < 2:

        await interaction.response.send_message(
            "❌ En az 2 seçenek yazmalısın.\n"
            "Örnek: `kırmızı, mavi, yeşil`",
            ephemeral=True
        )

        return

    sonuc = random.choice(
        secenekler_liste
    )

    await interaction.response.send_message(
        f"🎯 Seçimim: **{sonuc}**"
    )


@bot.tree.command(
    name="rate",
    description="Bir şeyi 10 üzerinden değerlendirir."
)
async def rate(
    interaction: discord.Interaction,
    sey: str
):

    puan = random.randint(
        1,
        10
    )

    await interaction.response.send_message(
        f"⭐ **{sey}** → `{puan}/10`"
    )


@bot.tree.command(
    name="random",
    description="İki sayı arasında rastgele sayı seçer."
)
async def random_number(
    interaction: discord.Interaction,
    minimum: int,
    maksimum: int
):

    if minimum > maksimum:

        await interaction.response.send_message(
            "❌ Minimum maksimumdan büyük olamaz.",
            ephemeral=True
        )

        return

    sonuc = random.randint(
        minimum,
        maksimum
    )

    await interaction.response.send_message(
        f"🎲 Sonuç: **{sonuc}**"
    )


@bot.tree.command(
    name="reverse",
    description="Yazıyı ters çevirir."
)
async def reverse(
    interaction: discord.Interaction,
    metin: str
):

    await interaction.response.send_message(
        metin[::-1]
    )


@bot.tree.command(
    name="say",
    description="Verilen yazıyı gönderir."
)
@app_commands.checks.has_permissions(
    manage_messages=True
)
async def say(
    interaction: discord.Interaction,
    metin: str
):

    await interaction.response.send_message(
        "✅ Gönderildi.",
        ephemeral=True
    )

    await interaction.channel.send(
        metin
    )


# ============================================================
# POLL
# ============================================================

@bot.tree.command(
    name="poll",
    description="Anket oluşturur."
)
async def poll(
    interaction: discord.Interaction,
    soru: str
):

    embed = discord.Embed(
        title="📊 ANKET",
        description=soru,
        color=PURPLE
    )

    embed.set_footer(
        text=f"{BOT_NAME} Poll System"
    )

    mesaj = await interaction.channel.send(
        embed=embed
    )

    await mesaj.add_reaction("✅")
    await mesaj.add_reaction("❌")

    await interaction.response.send_message(
        "📊 Anket oluşturuldu.",
        ephemeral=True
    )


# ============================================================
# AFK
# ============================================================

@bot.tree.command(
    name="afk",
    description="AFK durumuna geçer."
)
async def afk(
    interaction: discord.Interaction,
    sebep: str = "AFK"
):

    db_execute(
        """
        INSERT OR REPLACE INTO afk
        (user_id, reason, created_at)
        VALUES (?, ?, ?)
        """,
        (
            interaction.user.id,
            sebep,
            int(time.time())
        )
    )

    await interaction.response.send_message(
        f"💤 AFK oldun.\n**Sebep:** {sebep}"
    )


# ============================================================
# AYARLAR / SUNUCU
# ============================================================

def get_guild_setting(
    guild_id,
    field
):

    allowed = {
        "log_channel",
        "welcome_channel",
        "goodbye_channel",
        "autorole"
    }

    if field not in allowed:
        return 0

    row = db_execute(
        f"""
        SELECT {field}
        FROM guild_settings
        WHERE guild_id = ?
        """,
        (guild_id,),
        commit=False
    ).fetchone()

    if not row:

        db_execute(
            """
            INSERT INTO guild_settings
            (guild_id)
            VALUES (?)
            """,
            (guild_id,)
        )

        return 0

    return row[0]


def set_guild_setting(
    guild_id,
    field,
    value
):

    allowed = {
        "log_channel",
        "welcome_channel",
        "goodbye_channel",
        "autorole"
    }

    if field not in allowed:
        return

    db_execute(
        """
        INSERT OR IGNORE INTO guild_settings
        (guild_id)
        VALUES (?)
        """,
        (guild_id,)
    )

    db_execute(
        f"""
        UPDATE guild_settings
        SET {field} = ?
        WHERE guild_id = ?
        """,
        (
            value,
            guild_id
        )
    )


@bot.tree.command(
    name="logchannel",
    description="Log kanalını ayarlar."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def logchannel(
    interaction: discord.Interaction,
    kanal: discord.TextChannel
):

    set_guild_setting(
        interaction.guild.id,
        "log_channel",
        kanal.id
    )

    await interaction.response.send_message(
        f"📜 Log kanalı {kanal.mention} olarak ayarlandı."
    )


@bot.tree.command(
    name="welcomechannel",
    description="Hoş geldin kanalını ayarlar."
)
@app_commands.checks.has_permissions(
    manage_guild=True
)
async def welcomechannel(
    interaction: discord.Interaction,
    kanal: discord.TextChannel
):

    set_guild_setting(
        interaction.guild.id,
        "welcome_channel",
        kanal.id
    )

    await interaction.response.send_message(
        f"👋 Hoş geldin kanalı {kanal.mention} oldu."
    )


@bot.tree.command(
    name="autorole",
    description="Yeni üyelere otomatik rol verir."
)
@app_commands.checks.has_permissions(
    manage_roles=True
)
async def autorole(
    interaction: discord.Interaction,
    rol: discord.Role
):

    if rol >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ Bu rolü veremem.",
            ephemeral=True
        )

        return

    set_guild_setting(
        interaction.guild.id,
        "autorole",
        rol.id
    )

    await interaction.response.send_message(
        f"🎭 Otorol `{rol.name}` olarak ayarlandı."
    )


# ============================================================
# BOT BİLGİ
# ============================================================

BOT_START_TIME = datetime.now(
    timezone.utc
)


@bot.tree.command(
    name="ping",
    description="Bot gecikmesini gösterir."
)
async def ping(
    interaction: discord.Interaction
):

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(
        f"🏓 Pong!\n"
        f"📡 Gecikme: `{latency}ms`"
    )


@bot.tree.command(
    name="botinfo",
    description="Bot bilgilerini gösterir."
)
async def botinfo(
    interaction: discord.Interaction
):

    uptime = (
        datetime.now(
            timezone.utc
        )
        - BOT_START_TIME
    )

    embed = discord.Embed(
        title=f"💜 {BOT_NAME}",
        color=PURPLE
    )

    embed.description = (
        f"🤖 **Bot:** {bot.user}\n"
        f"🆔 **ID:** `{bot.user.id}`\n"
        f"🌐 **Sunucular:** `{len(bot.guilds)}`\n"
        f"👥 **Kullanıcılar:** "
        f"`{sum(g.member_count or 0 for g in bot.guilds)}`\n"
        f"⏱️ **Uptime:** `{str(uptime).split('.')[0]}`\n"
        f"⚡ **Ping:** `{round(bot.latency * 1000)}ms`"
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="serverstats",
    description="Sunucu istatistiklerini gösterir."
)
async def serverstats(
    interaction: discord.Interaction
):

    guild = interaction.guild

    humans = len([
        m for m in guild.members
        if not m.bot
    ])

    bots = len([
        m for m in guild.members
        if m.bot
    ])

    text_channels = len(
        guild.text_channels
    )

    voice_channels = len(
        guild.voice_channels
    )

    roles = len(
        guild.roles
    )

    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=PURPLE
    )

    embed.add_field(
        name="👥 İnsan",
        value=f"`{humans}`",
        inline=True
    )

    embed.add_field(
        name="🤖 Bot",
        value=f"`{bots}`",
        inline=True
    )

    embed.add_field(
        name="💬 Yazı Kanalı",
        value=f"`{text_channels}`",
        inline=True
    )

    embed.add_field(
        name="🔊 Ses Kanalı",
        value=f"`{voice_channels}`",
        inline=True
    )

    embed.add_field(
        name="🎭 Roller",
        value=f"`{roles}`",
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# OTOMATİK MESAJ / WELCOME
# ============================================================

@bot.event
async def on_member_join(member):

    guild = member.guild

    ayarlar = dashboard_settings(
        guild.id
    )

    # --------------------------------------------------------
    # OTOROL
    # --------------------------------------------------------

    autorole_id = ayarlar.get(
        "autorole",
        0
    )

    if autorole_id:

        rol = guild.get_role(
            int(autorole_id)
        )

        if rol and rol < guild.me.top_role:

            try:

                await member.add_roles(
                    rol,
                    reason="Veloria Dashboard Otorol"
                )

            except Exception as e:

                print(
                    "OTOROL HATASI:",
                    e
                )

    # --------------------------------------------------------
    # HOŞ GELDİN
    # --------------------------------------------------------

    welcome_id = ayarlar.get(
        "welcome_channel",
        0
    )

    if welcome_id:

        kanal = guild.get_channel(
            int(welcome_id)
        )

        if kanal:

            try:

                await kanal.send(
                    f"👋 Hoş geldin "
                    f"{member.mention}!\n"
                    f"💜 **{guild.name}** sunucusuna katıldın."
                )

            except Exception as e:

                print(
                    "HOŞ GELDİN HATASI:",
                    e
                )

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    await dashboard_log(
        guild,
        (
            f"📥 **Üye Katıldı**\n"
            f"👤 {member.mention}\n"
            f"🆔 `{member.id}`"
        )
    )

    # --------------------------------------------------------
    # ANTI RAID
    # --------------------------------------------------------

    if ayarlar.get(
        "anti_raid",
        0
    ):

        simdi = time.time()

        joins = RAID_JOINS.setdefault(
            guild.id,
            []
        )

        joins.append(
            simdi
        )

        joins[:] = [
            t for t in joins
            if simdi - t <= 10
        ]

        if len(joins) >= 5:

            await dashboard_log(
                guild,
                (
                    "🚨 **ANTI-RAID UYARISI**\n"
                    f"Son 10 saniyede `{len(joins)}` "
                    "yeni üye katıldı.\n"
                    "Sunucuda olağandışı giriş algılandı."
                )
            )


# ============================================================
# MESAJ İSTATİSTİĞİ + AFK + DASHBOARD + AUTORESPONSE + XP
# ============================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # --------------------------------------------------------
    # SUNUCU KONTROLÜ
    # --------------------------------------------------------

    if message.guild:

        guild = message.guild

        ayarlar = dashboard_settings(
            guild.id
        )

        # ----------------------------------------------------
        # LINK FİLTRESİ
        # ----------------------------------------------------

        if (
            ayarlar.get(
                "anti_link",
                0
            )
            and link_var_mi(
                message.content
            )
            and not message.author.guild_permissions.manage_messages
        ):

            try:

                await message.delete()

                await message.channel.send(
                    f"🚫 {message.author.mention} "
                    "link göndermek yasak.",
                    delete_after=5
                )

                await dashboard_log(
                    guild,
                    (
                        "🔗 **Link Engellendi**\n"
                        f"👤 {message.author.mention}\n"
                        f"💬 `{message.content[:300]}`"
                    )
                )

            except discord.Forbidden:

                print(
                    "[FİLTRE] Botun mesaj silme yetkisi yok."
                )

            return

        # ----------------------------------------------------
        # KÜFÜR FİLTRESİ
        # ----------------------------------------------------

        if (
            ayarlar.get(
                "profanity_filter",
                0
            )
            and kufur_var_mi(
                message.content
            )
            and not message.author.guild_permissions.manage_messages
        ):

            try:

                await message.delete()

                await message.channel.send(
                    f"⚠️ {message.author.mention} "
                    "küfür filtresine takıldın.",
                    delete_after=5
                )

                await dashboard_log(
                    guild,
                    (
                        "🤬 **Küfür Engellendi**\n"
                        f"👤 {message.author.mention}\n"
                        f"💬 `{message.content[:300]}`"
                    )
                )

            except discord.Forbidden:

                print(
                    "[FİLTRE] Botun mesaj silme yetkisi yok."
                )

            return

        # ----------------------------------------------------
        # ANTI SPAM
        # ----------------------------------------------------

        if (
            ayarlar.get(
                "anti_spam",
                0
            )
            and not message.author.guild_permissions.manage_messages
        ):

            uid_spam = message.author.id

            simdi_spam = time.time()

            mesajlar = SPAM_MESSAGES.setdefault(
                (guild.id, uid_spam),
                []
            )

            mesajlar.append(
                simdi_spam
            )

            mesajlar[:] = [
                t for t in mesajlar
                if simdi_spam - t <= 5
            ]

            # 5 saniyede 6 mesaj
            if len(mesajlar) >= 6:

                try:

                    await message.delete()

                except Exception:
                    pass

                try:

                    await message.author.timeout(
                        timedelta(seconds=10),
                        reason="Veloria Anti-Spam"
                    )

                except discord.Forbidden:

                    print(
                        "[ANTI-SPAM] Timeout yetkisi yok."
                    )

                await dashboard_log(
                    guild,
                    (
                        "🚨 **ANTI-SPAM**\n"
                        f"👤 {message.author.mention}\n"
                        "10 saniyelik timeout uygulandı."
                    )
                )

                SPAM_MESSAGES.pop(
                    (guild.id, uid_spam),
                    None
                )

                return

    # --------------------------------------------------------
    # MESAJ İSTATİSTİĞİ
    # --------------------------------------------------------

    uid = message.author.id

    message_stats[uid] = (
        message_stats.get(
            uid,
            0
        )
        + 1
    )

    # --------------------------------------------------------
    # AFK KALDIR
    # --------------------------------------------------------

    afk_row = db_execute(
        """
        SELECT reason
        FROM afk
        WHERE user_id = ?
        """,
        (uid,),
        commit=False
    ).fetchone()

    if afk_row:

        db_execute(
            """
            DELETE FROM afk
            WHERE user_id = ?
            """,
            (uid,)
        )

        try:

            await message.channel.send(
                f"👋 Tekrar hoş geldin "
                f"{message.author.mention}!"
            )

        except Exception:
            pass

    # --------------------------------------------------------
    # ETİKETLENEN KULLANICI AFK MI
    # --------------------------------------------------------

    for user in message.mentions:

        afk_data = db_execute(
            """
            SELECT reason, created_at
            FROM afk
            WHERE user_id = ?
            """,
            (user.id,),
            commit=False
        ).fetchone()

        if afk_data:

            reason, created_at = afk_data

            try:

                await message.channel.send(
                    f"💤 **{user.display_name}** "
                    "şu anda AFK.\n"
                    f"Sebep: **{reason}**\n"
                    f"<t:{created_at}:R>"
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # XP
    # --------------------------------------------------------

    simdi = datetime.now(
        timezone.utc
    ).timestamp()

    son_xp = XP_COOLDOWN.get(
        uid,
        0
    )

    if simdi - son_xp >= 60:

        XP_COOLDOWN[uid] = simdi

        miktar = random.randint(
            10,
            25
        )

        seviye_atladi = xp_ekle(
            uid,
            miktar
        )

        if seviye_atladi:

            try:

                yeni_seviye = get_xp(
                    uid
                )["level"]

                await message.channel.send(
                    f"🎉 {message.author.mention} "
                    "**seviye atladı!** ⭐\n"
                    f"Yeni seviyen: **{yeni_seviye}**"
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # OTOMATİK CEVAPLAR
    # --------------------------------------------------------

    if message.guild:

        content = message.content.lower().strip()

        default_replies = {

            "selam": [
                "Selam la 😎",
                "Selam kral",
                "Ooo selam"
            ],

            "sa": [
                "Aleyküm selam 😎",
                "Aleyküm selam kral"
            ],

            "naber": [
                "İyidir la senden naber?",
                "İyiyim kral sen nasılsın?",
                "Takılıyoz işte 😎"
            ],

            "nasılsın": [
                "İyiyim la sen?",
                "İyidir kral 😎",
                "Gayet iyiyim"
            ],

            "iyi misin": [
                "İyiyim la sen?",
                "İyidir kral"
            ]
        }

        if content in default_replies:

            cevap = random.choice(
                default_replies[content]
            )

            try:

                await message.channel.send(
                    cevap
                )

            except Exception:
                pass

    await bot.process_commands(
        message
    )


# ============================================================
# YARDIM
# ============================================================

@bot.tree.command(
    name="yardım",
    description="Bot komutlarını gösterir."
)
async def yardim(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title=f"💜 {BOT_NAME}",
        description=(
            "Discord bot komutları\n"
            "Aşağıdaki sistemlerden birini kullanabilirsin."
        ),
        color=PURPLE
    )

    embed.add_field(
        name="🎧 Müzik",
        value=(
            "`/play`\n"
            "`/müzik`\n"
            "`/skip`\n"
            "`/pause`\n"
            "`/resume`\n"
            "`/stop`\n"
            "`/kuyruk`\n"
            "`/shuffle`\n"
            "`/loop`\n"
            "`/ses`\n"
            "`/join`\n"
            "`/leave`\n"
            "`/clearqueue`\n"
            "`/nowplaying`\n"
            "`/remove`"
        ),
        inline=True
    )

    embed.add_field(
        name="🛡️ Moderasyon",
        value=(
            "`/sil`\n"
            "`/purge`\n"
            "`/kick`\n"
            "`/ban`\n"
            "`/unban`\n"
            "`/timeout`\n"
            "`/untimeout`\n"
            "`/slowmode`\n"
            "`/lock`\n"
            "`/unlock`\n"
            "`/warn`\n"
            "`/warnings`\n"
            "`/clearwarnings`\n"
            "`/nick`\n"
            "`/rolver`\n"
            "`/rolal`"
        ),
        inline=True
    )

    embed.add_field(
        name="💰 Ekonomi",
        value=(
            "`/bakiye`\n"
            "`/günlük`\n"
            "`/weekly`\n"
            "`/work`\n"
            "`/give`\n"
            "`/leaderboard`"
        ),
        inline=True
    )

    embed.add_field(
        name="⭐ XP",
        value=(
            "`/seviye`\n"
            "`/rank`"
        ),
        inline=True
    )

    embed.add_field(
        name="🎮 Eğlence",
        value=(
            "`/coinflip`\n"
            "`/dice`\n"
            "`/8ball`\n"
            "`/choose`\n"
            "`/rate`\n"
            "`/random`\n"
            "`/reverse`\n"
            "`/poll`"
        ),
        inline=True
    )

    embed.add_field(
        name="👤 Bilgi",
        value=(
            "`/avatar`\n"
            "`/banner`\n"
            "`/kullanıcıbilgi`\n"
            "`/sunucubilgi`\n"
            "`/roleinfo`\n"
            "`/serverstats`\n"
            "`/botinfo`\n"
            "`/ping`"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️ Sistem",
        value=(
            "`/afk`\n"
            "`/logchannel`\n"
            "`/welcomechannel`\n"
            "`/autorole`"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# HATA SİSTEMİ
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    print(
        "KOMUT HATASI:",
        repr(error)
    )

    if isinstance(
        error,
        app_commands.MissingPermissions
    ):

        mesaj = (
            "❌ Bu komut için gerekli yetkin yok."
        )

    elif isinstance(
        error,
        app_commands.BotMissingPermissions
    ):

        mesaj = (
            "❌ Botun bu komut için gerekli yetkisi yok."
        )

    elif isinstance(
        error,
        app_commands.CommandOnCooldown
    ):

        mesaj = (
            "⏳ Bu komutu tekrar kullanmadan önce bekle."
        )

    else:

        mesaj = (
            "❌ Komut çalıştırılırken bir hata oluştu."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                mesaj,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                mesaj,
                ephemeral=True
            )

    except Exception:
        pass


# ============================================================
# /SUNUCU-KUR - GÜVENLİ SUNUCU DÜZENLEME
# ============================================================

SUNUCU_KUR_YAPISI = [
    ("🛡️ YÖNETİM MERKEZİ", "staff", [
        ("text", "⌈💬⌋・mod-sohbet"), ("voice", "⌈🔊⌋・mod-toplantı"),
        ("text", "⌈🧪⌋・deneme-mod"), ("text", "⌈⚙️⌋・mod-komut"),
        ("text", "⌈📢⌋・mod-duyuru"), ("text", "⌈💬⌋・mod-chat")]),
    ("📊 SUNUCU BİLGİLERİ", "locked", [
        ("text", "⌈📊⌋・sunucu-paneli"), ("text", "⌈👥⌋・üye-sayısı"),
        ("text", "⌈📜⌋・kurallar"), ("text", "⌈📢⌋・duyurular"),
        ("text", "⌈🎉⌋・çekilişler"), ("text", "⌈🚀⌋・sunucu-takviye"),
        ("text", "⌈🎭⌋・rol-al")]),
    ("💬 GENEL ALAN", "public", [
        ("text", "⌈💬⌋・genel-sohbet"), ("text", "⌈🤖⌋・bot-komutları"),
        ("text", "⌈🖼️⌋・galeri"), ("text", "⌈📈⌋・level-up"),
        ("voice", "⌈🔊⌋・sohbet"), ("voice", "⌈🔊⌋・sohbet-2"),
        ("voice", "⌈🔊⌋・sohbet-3"), ("voice", "⌈🔊⌋・sohbet-4"),
        ("voice", "⌈🔊⌋・sohbet-5"), ("voice", "⌈🎵⌋・müzik-1"),
        ("voice", "⌈🎵⌋・müzik-2"), ("voice", "⌈🎵⌋・müzik-3"),
        ("voice", "⌈🎵⌋・müzik-4"), ("voice", "⌈🧠⌋・overthink"),
        ("voice", "⌈💤⌋・afk")]),
    ("🎮 LEAGUE OF LEGENDS", "public", [
        ("text", "⌈🔎⌋・lol-duo-bulma")] +
        [("text", "⌈💬⌋・lol-sohbet-" + str(i)) for i in range(1, 6)]),
    ("🎯 VALORANT", "public", [
        ("text", "⌈🔎⌋・valorant-duo-bulma")] +
        [("text", "⌈💬⌋・valorant-sohbet-" + str(i)) for i in range(1, 6)]),
    ("⛏️ MINECRAFT", "public", [
        ("text", "⌈🔎⌋・minecraft-duo-bulma")] +
        [("text", "⌈💬⌋・minecraft-sohbet-" + str(i)) for i in range(1, 6)]),
    ("🎉 EĞLENCE", "public", [
        ("text", "⌈🔢⌋・sayı-sayma"), ("text", "⌈🎯⌋・tuttu-tutmadı"),
        ("text", "⌈🔤⌋・kelime-türetme")]),
    ("👋 HOŞ GELDİN", "locked", [
        ("text", "⌈👋⌋・hoş-geldin"), ("text", "⌈📥⌋・giriş-çıkış")]),
    ("🤝 PARTNERLİK", "public", [
        ("text", "⌈🤝⌋・partnerlerimiz"), ("text", "⌈📃⌋・partnerlik-textimiz")]),
    ("📑 LOG SİSTEMİ", "locked", [
        ("text", "⌈💬⌋・mesaj-log"), ("text", "⌈👤⌋・üye-log"),
        ("text", "⌈🎭⌋・rol-log"), ("text", "⌈🗂️⌋・kanal-log"),
        ("text", "⌈🛡️⌋・yetkili-log"), ("text", "⌈🔊⌋・ses-log")])
]

SUNUCU_KUR_KORUNAN = ("kural", "rule", "partner", "community", "topluluk")


def sunucu_kur_korunan_kategori(category):
    names = [category.name] + [channel.name for channel in category.channels]
    return any(word in name.casefold() for name in names for word in SUNUCU_KUR_KORUNAN)


def sunucu_kur_izinleri(guild, kind):
    if kind == "staff":
        result = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
        for name in ("Baba", "+", "Üst Yetkili", "Admin", "Moderatör", "Deneme Moderatör", "Mod Ekibi"):
            role = discord.utils.get(guild.roles, name=name)
            if role:
                result[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    connect=True, speak=True
                )
        return result
    if kind == "locked":
        result = {guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, add_reactions=False,
            create_public_threads=False, create_private_threads=False,
            send_messages_in_threads=False
        )}
        for role in guild.roles:
            if not role.is_default():
                result[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, add_reactions=False,
                    create_public_threads=False, create_private_threads=False,
                    send_messages_in_threads=False
                )
        for name in ("Baba", "Üst Yetkili"):
            role = discord.utils.get(guild.roles, name=name)
            if role:
                result[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    add_reactions=True, create_public_threads=False,
                    create_private_threads=False, send_messages_in_threads=False
                )
        return result
    return {}


def sunucu_kur_silinecekler(guild):
    return [c for c in guild.categories if not sunucu_kur_korunan_kategori(c)]


def sunucu_kur_onizleme(guild, mode):
    lines = []
    if mode == "reset":
        lines.append("SİLİNECEK KATEGORİLER VE KANALLARI:")
        targets = sunucu_kur_silinecekler(guild)
        for cat in targets:
            lines.append("- " + cat.name + ": " + (", ".join(ch.name for ch in cat.channels) or "Boş"))
        if not targets:
            lines.append("Silinecek kategori bulunamadı.")
        lines.append("Kurallar, partnerlik ve Community alanları korunur.")
    else:
        lines.append("Mevcut kategoriler silinmeyecek; yalnızca eksikler oluşturulacak.")
    lines.append("")
    lines.append("OLUŞTURULACAK DÜZEN:")
    for name, kind, channels in SUNUCU_KUR_YAPISI:
        lines.append(name)
        lines.extend(("🔊 " if typ == "voice" else "💬 ") + ch for typ, ch in channels)
    result = "\n".join(lines)
    return result[:3900] + "\n… Liste kısaltıldı." if len(result) > 3900 else result


async def sunucu_kur_uygula(guild, mode):
    made_cats = made_channels = removed_cats = 0
    if mode == "reset":
        for cat in list(sunucu_kur_silinecekler(guild)):
            await cat.delete(reason="/sunucu-kur: ikinci onay")
            removed_cats += 1
    for name, kind, channels in SUNUCU_KUR_YAPISI:
        cat = discord.utils.get(guild.categories, name=name)
        if cat is None:
            cat = await guild.create_category(
                name, overwrites=sunucu_kur_izinleri(guild, kind),
                reason="/sunucu-kur: kategori oluşturma"
            )
            made_cats += 1
        for typ, channel_name in channels:
            if discord.utils.get(cat.channels, name=channel_name):
                continue
            if typ == "voice":
                await guild.create_voice_channel(channel_name, category=cat)
            else:
                await guild.create_text_channel(
                    channel_name, category=cat,
                    overwrites=sunucu_kur_izinleri(guild, kind)
                )
            made_channels += 1
    return made_cats, made_channels, removed_cats


class SunucuKurOnayView(discord.ui.View):
    def __init__(self, mode, owner_id):
        super().__init__(timeout=180)
        self.mode, self.owner_id = mode, owner_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Bu paneli yalnızca başlatan kişi kullanabilir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Onayla ve uygula", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        if not interaction.guild:
            await interaction.response.send_message("Sunucu bulunamadı.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            cats, chans, deleted = await sunucu_kur_uygula(interaction.guild, self.mode)
            await interaction.followup.send(
                "Kurulum tamamlandı. Oluşturulan kategori: " + str(cats) +
                ", oluşturulan kanal: " + str(chans) +
                ", silinen kategori: " + str(deleted) + ".",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("Botun kanal/kategori yönetme izni yok.", ephemeral=True)
        except Exception as error:
            print("SUNUCU KUR HATASI:", error)
            await interaction.followup.send("Hata oluştu; ayrıntı konsola yazıldı. Kısmi değişiklikler olabilir.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="İptal", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="İptal edildi; değişiklik yapılmadı.", embed=None, view=None)
        self.stop()


class SunucuKurSecimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="Kurulum türünü seç...", min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="Komple sunucu düzeni", value="complete"),
            discord.SelectOption(label="Kategorileri sıfırla", value="reset"),
            discord.SelectOption(label="Kategorileri değiştir", value="modify")
        ]
    )
    async def select_mode(self, interaction, select):
        mode = select.values[0]
        embed = discord.Embed(
            title="💜 VELORIA — KURULUM ÖNİZLEMESİ",
            description=sunucu_kur_onizleme(interaction.guild, mode),
            color=PURPLE
        )
        embed.set_footer(text="İkinci onay olmadan hiçbir işlem yapılmaz.")
        await interaction.response.edit_message(
            content="Etkilenecek alanları kontrol et:", embed=embed,
            view=SunucuKurOnayView(mode, interaction.user.id)
        )


@bot.tree.command(name="sunucu-kur", description="Veloria sunucusunun kanal düzenini güvenli şekilde oluşturur.")
async def sunucu_kur(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("Bu komut yalnızca sunucuda kullanılabilir.", ephemeral=True)
        return
    baba = discord.utils.get(guild.roles, name="Baba")
    ust = discord.utils.get(guild.roles, name="Üst Yetkili")
    roles = getattr(interaction.user, "roles", [])
    if not any(role and role in roles for role in (baba, ust)):
        await interaction.response.send_message("Bu komutu yalnızca Baba veya Üst Yetkili kullanabilir.", ephemeral=True)
        return
    if not guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("Botta Kanalları Yönet izni bulunmuyor.", ephemeral=True)
        return
    await interaction.response.send_message(
        "💜 VELORIA SUNUCU KURULUMU\nİşlem türünü seç. Önce etkilenecek alanları göstereceğim; ikinci onayından önce değişiklik yapılmayacak.",
        view=SunucuKurSecimView(), ephemeral=True
    )

# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print()

    print(
        "=" * 60
    )

    print(
        f"              {BOT_NAME} BAŞLATILDI"
    )

    print(
        "=" * 60
    )

    print(
        f"Bot: {bot.user}"
    )

    print(
        f"ID: {bot.user.id}"
    )

    if FFMPEG_PATH:

        print(
            "FFmpeg: BULUNDU"
        )

        print(
            f"FFmpeg yolu: {FFMPEG_PATH}"
        )

    else:

        print(
            "FFmpeg: BULUNAMADI!"
        )

    print(
        f"Sunucu Sayısı: {len(bot.guilds)}"
    )

    print(
        "=" * 60
    )

    try:

        synced = await bot.tree.sync()

        print(
            f"{len(synced)} slash komutu senkronlandı."
        )

    except Exception as e:

        print(
            "SLASH KOMUT HATASI:",
            e
        )

    try:

        bot.add_view(
            MuzikPanel()
        )

        print(
            "Müzik panel butonları hazır."
        )

    except Exception as e:

        print(
            "VIEW HATASI:",
            e
        )


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
