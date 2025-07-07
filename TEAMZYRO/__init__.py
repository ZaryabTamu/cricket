# ------------------------------ IMPORTS ---------------------------------
import logging
import os
from telegram.ext import Application
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters as f
from pyrogram.types import x

# --------------------------- LOGGING SETUP ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt"),
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)

# ---------------------------- CONSTANTS ---------------------------------
api_id = 28731656
api_hash = "22f05593e2f2f365ebc1fcc03446a8c8"


TOKEN = "7392456702:AAEPBt5qkAaP5edIg5_wP3kI00ERdeoH3KA"
CHARA_CHANNEL_ID = "none2025databese"
GLOG = CHARA_CHANNEL_ID

SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "-1002309742084")
mongo_url = "mongodb+srv://harshmanjhi1801:webapp@cluster0.xxwc4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"


MUSJ_JOIN = os.getenv("MUSJ_JOIN", "username")

# Modified to support both image and video URLs
START_MEDIA = os.getenv("START_MEDIA", "https://files.catbox.moe/7ccoub.jpg,https://telegra.ph/file/1a3c152717eb9d2e94dc2.mp4").split(',')

PHOTO_URL = [
    os.getenv("PHOTO_URL_1", "https://files.catbox.moe/7ccoub.jpg"),
    os.getenv("PHOTO_URL_2", "https://files.catbox.moe/7ccoub.jpg")
]

STATS_IMG = ["https://files.catbox.moe/gknnju.jpg"] 

SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/Zyroupdates")
UPDATE_CHAT = os.getenv("UPDATE_CHAT", "https://t.me/ZyroBotCodes")
SUDO = list(map(int, os.getenv("SUDO", "7577185215,5749187175").split(',')))
OWNER_ID = int(os.getenv("OWNER_ID", "7073835511"))

# --------------------- TELEGRAM BOT CONFIGURATION -----------------------
command_filter = f.create(lambda _, __, message: message.text and message.text.startswith("/"))
application = Application.builder().token(TOKEN).build()
ZYRO = Client("Shivu", api_id=api_id, api_hash=api_hash, bot_token=TOKEN)

# -------------------------- DATABASE SETUP ------------------------------
ddw = AsyncIOMotorClient(mongo_url)
db = ddw['gaming_create']

# Collections
user_totals_collection = db['gaming_totals']
group_user_totals_collection = db['gaming_group_total1']
top_global_groups_collection = db['gaming_global_groups1']
pm_users = db['gaming_pm_users1']
destination_collection = db['gamimg_user_collection1']
destination_char = db['gaming_anime_characters']

# -------------------------- GLOBAL VARIABLES ----------------------------
app = ZYRO
sudo_users = SUDO
collection = destination_char
user_collection = destination_collection
x = x
# --------------------------- STRIN ---------------------------------------
locks = {}
message_counters = {}
spam_counters = {}
last_characters = {}
sent_characters = {}
first_correct_guesses = {}
message_counts = {}
last_user = {}
warned_users = {}
user_cooldowns = {}
user_nguess_progress = {}
user_guess_progress = {}
normal_message_counts = {}  

# -------------------------- POWER SETUP --------------------------------
from TEAMZYRO.unit.zyro_ban import *
from TEAMZYRO.unit.zyro_sudo import *
from TEAMZYRO.unit.zyro_react import *
from TEAMZYRO.unit.zyro_log import *
from TEAMZYRO.unit.zyro_send_img import *
from TEAMZYRO.unit.zyro_rarity import *
# ------------------------------------------------------------------------

async def PLOG(text: str):
    await app.send_message(
       chat_id=GLOG,
       text=text
   )

# ---------------------------- END OF CODE ------------------------------
