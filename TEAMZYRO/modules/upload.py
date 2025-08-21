import os
import requests
from pyrogram import Client, filters
from pymongo import ReturnDocument
from gridfs import GridFS
from TEAMZYRO import application, CHARA_CHANNEL_ID, SUPPORT_CHAT, OWNER_ID, collection, user_collection, db, SUDO, rarity_map, ZYRO, require_power

# Define the wrong format message and rarity map
WRONG_FORMAT_TEXT = """❌ Wrong format!

✅ Correct usage:
Reply to a photo and send:
`/upload Virat-Kohli Royal-Challengers-Bengaluru 10`

📌 Format:
`/upload cricketer-name team-name rarity-number`

📝 Notes:
• Use hyphens `-` between words (no spaces).
• `rarity-number` must be chosen from the map below.

rarity_map = {
    1: "⚪ Common",
    2: "⭐ Basic",
    3: "⚡ Standard",
    4: "🟢 Medium",
    5: "🟣 Rare",
    6: "🟡 Legendary",
    7: "🌟 Uncommon",
    8: "💮 Special Edition",
    9: "🍃 Ghibli",
    10: "⚜ Royal",
    11: "🎃 X Verse",
    12: "🌌 Cosmic",
    13: "🔮 Limited Edition",
    14: "❄️ Ethereal",
    15: "🔱 Ultimate",
    16: "♾️ Immortal Teams",
    17: "🧿 Premium",
    18: "👑 Supreme"
}
"""


async def find():
    cursor = collection.find().sort('id', 1)
    ids = []

    async for doc in cursor:
        if 'id' in doc:
            ids.append(int(doc['id']))

    # Check for gaps in the sequence
    ids.sort()
    for i in range(1, len(ids) + 2):  # Include one extra for the next ID if no gaps
        if i not in ids:
            return str(i).zfill(2)  # Return the missing ID

    return str(len(ids) + 1).zfill(2)  # If no gaps, return the next sequential ID


# Function to find the next available ID for a character
async def find_available_id():
    cursor = collection.find().sort('id', 1)
    ids = []

    async for doc in cursor:
        if 'id' in doc:
            ids.append(int(doc['id']))

    # Check for gaps in the sequence
    ids.sort()
    for i in range(1, len(ids) + 2):  # Include one extra for the next ID if no gaps
        if i not in ids:
            return str(i).zfill(2)  # Return the missing ID

    return str(len(ids) + 1).zfill(2)  # If no gaps, return the next sequential ID


def upload_to_catbox(file_path=None, file_url=None, expires=None, secret=None):
    url = "https://catbox.moe/user/api.php"
    with open(file_path, "rb") as file:
        response = requests.post(
            url,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": file}
        )
        if response.status_code == 200 and response.text.startswith("https"):
            return response.text
        else:
            raise Exception(f"Error uploading to Catbox: {response.text}")

@ZYRO.on_message(filters.command(["find"]))
@require_power("add_character")
async def ul(client, message):
    available_id = await find()
    await message.reply_text(
                f"new id {available_id}"
            )
    

import asyncio

upload_lock = asyncio.Lock()  # Lock for handling concurrent uploads

@ZYRO.on_message(filters.command(["upload"]))
@require_power("add_character")
async def ul(client, message):
    global upload_lock

    if upload_lock.locked():
        await message.reply_text("Another upload is in progress. Please wait until it is completed.")
        return

    async with upload_lock:  # Acquire lock
        reply = message.reply_to_message
        if reply and (reply.photo or reply.document or reply.video):
            args = message.text.split()
            if len(args) != 4:
                await client.send_message(chat_id=message.chat.id, text=WRONG_FORMAT_TEXT)
                return

            # Extract character details from the command arguments
            character_name = args[1].replace('-', ' ').title()
            anime = args[2].replace('-', ' ').title()
            rarity = int(args[3])

            # Validate rarity value
            if rarity not in rarity_map:
                await message.reply_text("Invalid rarity value. Please use a value between 1 and 18.")
                return

            rarity_text = rarity_map[rarity]
            available_id = await find_available_id()

            # Prepare character data
            character = {
                'name': character_name,
                'anime': anime,
                'rarity': rarity_text,
                'id': available_id
            }

            processing_message = await message.reply("<ᴘʀᴏᴄᴇꜱꜱɪɴɢ>....")
            path = await reply.download()
            try:
                # Upload image or video to Catbox
                catbox_url = upload_to_catbox(path)

                # Update character with the image or video URL
                if reply.photo or reply.document:
                    character['img_url'] = catbox_url
                elif reply.video:
                    character['vid_url'] = catbox_url
                    # Download and upload thumbnail
                    thumbnail_path = await client.download_media(reply.video.thumbs[0].file_id)
                    thumbnail_url = upload_to_catbox(thumbnail_path)
                    character['thum_url'] = thumbnail_url
                    os.remove(thumbnail_path)  # Clean up the thumbnail file

                # Send character details to the channel
                if reply.photo or reply.document:
                    await client.send_photo(
                        chat_id=CHARA_CHANNEL_ID,
                        photo=catbox_url,
                        caption=(
                            f"Character Name: {character_name}\n"
                            f"Team Name: {anime}\n"
                            f"Rarity: {rarity_text}\n"
                            f"ID: {available_id}\n"
                            f"Added by [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
                        ),
                    )
                elif reply.video:
                    await client.send_video(
                        chat_id=CHARA_CHANNEL_ID,
                        video=catbox_url,
                        caption=(
                            f"Character Name: {character_name}\n"
                            f"Team Name: {anime}\n"
                            f"Rarity: {rarity_text}\n"
                            f"ID: {available_id}\n"
                            f"Added by [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n"
                        ),
                    )

                # Insert character into the database
                await collection.insert_one(character)
                await message.reply_text(
                    f"➲ ᴀᴅᴅᴇᴅ ʙʏ» [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
                    f"➥ Character ID: {available_id}\n"
                    f"➥ Rarity: {rarity_text}"
                )
            except Exception as e:
                await message.reply_text(f"Character Upload Unsuccessful. Error: {str(e)}")
            finally:
                os.remove(path)  # Clean up the downloaded file
        else:
            await message.reply_text("Please reply to a photo, document, or video.")


