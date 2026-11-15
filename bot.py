from dotenv import load_dotenv
import os

print("[ENV TEST] .env yükleme:", load_dotenv("/home/container/.env"))
print("[ENV TEST] DISCORD_TOKEN bulundu:", bool(os.getenv("DISCORD_TOKEN")))
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

BOT_TOKEN = os.getenv("MTQ1NzA3MzI5OTkzMzc1NzQ5MA.GN3PRI.qxMSJTh76Emhnajy0QGB7YhkrbVV7A3vvqRShA")

if not BOT_TOKEN:
    raise RuntimeError("DISCORD_TOKEN ortam değişkeni ayarlanmamış!")

PREFIX = "!"

BOT_NAME = "VELORIA"
PURPLE = discord.Color.from_rgb(91, 33, 182)


# ============================================================
