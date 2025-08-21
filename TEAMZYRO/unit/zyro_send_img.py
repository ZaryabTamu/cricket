from TEAMZYRO import *
import random
import asyncio
import time
from telegram import Update
from telegram.ext import CallbackContext

log = "-1002992210309"

# Delete messages after 5 minutes
async def delete_message(chat_id, message_id, context):
    await asyncio.sleep(300)  # 5 minutes
    try:
        await context.bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Error deleting message: {e}")

# ✅ Rarity weights (Common 60% → Ethereal 0.1%)
RARITY_WEIGHTS = {
    "⚪ Common": (60, True),
    "⭐ Basic": (15, True),
    "⚡ Standard": (10, True),
    "🟢 Medium": (6, True),
    "🔥 Advanced": (4, True),
    "🟣 Rare": (2, True),
    "🟡 Legendary": (1.2, True),
    "🌟 Uncommon": (0.9, True),
    "💮 Special Edition": (0.7, True),
    "⚜ Royal": (0.2, True),
    "🎃 X Verse": (0.4, True),
    "🌌 Cosmic": (0.3, True),
    "🔮 Limited Edition": (0.2, True),
    "❄️ Ethereal": (0.1, True),
}

async def send_image(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id

    # ✅ Fetch only characters with rarities in RARITY_WEIGHTS
    all_characters = await collection.find(
        {"rarity": {"$in": list(RARITY_WEIGHTS.keys())}}
    ).to_list(length=None)

    if not all_characters:
        await context.bot.send_message(chat_id, "⚠️ No characters with allowed rarities found in the database.")
        return

    # ✅ Filter characters with enabled rarities
    available_characters = [
        c for c in all_characters
        if 'id' in c and c.get('rarity') in RARITY_WEIGHTS and RARITY_WEIGHTS[c['rarity']][1]
    ]

    if not available_characters:
        await context.bot.send_message(chat_id, "⚠️ No available characters with the allowed rarities.")
        return

    # ✅ Weighted random selection
    weights = [RARITY_WEIGHTS[c["rarity"]][0] for c in available_characters]
    selected_character = random.choices(available_characters, weights=weights, k=1)[0]

    # ✅ Track last character
    last_characters[chat_id] = selected_character
    last_characters[chat_id]['timestamp'] = time.time()

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]

    # ✅ Send video or photo
    if 'vid_url' in selected_character:
        sent_message = await context.bot.send_video(
            chat_id=chat_id,
            video=selected_character['vid_url'],
            caption=f"""✨ A {selected_character['rarity']} Character Appears! ✨

🔍 Use /guess to claim this mysterious Cricketer!
💫 Hurry, before someone else snatches them!""",
            parse_mode='Markdown'
        )
    else:
        sent_message = await context.bot.send_photo(
            chat_id=chat_id,
            photo=selected_character['img_url'],
            caption=f"""✨ A {selected_character['rarity']} Character Appears! ✨
🔍 Use /guess to claim this mysterious Cricketer!
💫 Hurry, before someone else snatches them!""",
            parse_mode='Markdown'
        )

    # ✅ Schedule message deletion after 5 minutes
    asyncio.create_task(delete_message(chat_id, sent_message.message_id, context))