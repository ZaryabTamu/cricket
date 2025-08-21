from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from TEAMZYRO import app, user_collection, collection
import random
import uuid

# --- SETTINGS ---
TOKEN_COST = 2  # 2 tokens per game (double mines)
RARITIES = [
    "⚪ Common", "⭐ Basic", "⚡ Standard", "🟢 Medium", "🟣 Rare",
    "🟡 Legendary", "🌟 Uncommon", "💮 Special Edition", "🍃 Ghibli", "🌌 Cosmic"
]

# In-memory game state
card_games = {}

# Start cards game
@app.on_message(filters.command("cards"))
async def start_cards(client: Client, message: Message):
    user_id = message.from_user.id
    user_data = await user_collection.find_one({'id': user_id}, {'tokens': 1})

    if not user_data or user_data.get('tokens', 0) < TOKEN_COST:
        await message.reply_text(f"You need {TOKEN_COST} tokens to play Cards! Use /redeemtoken to get tokens.")
        return

    # Deduct tokens
    await user_collection.update_one({'id': user_id}, {'$inc': {'tokens': -TOKEN_COST}})

    game_id = str(uuid.uuid4())
    chick_index = random.randint(0, 3)  # Which card is the 🐥

    card_games[user_id] = {"game_id": game_id, "chick_index": chick_index}

    keyboard = [[
        InlineKeyboardButton("🃏", callback_data=f"card_{game_id}_{user_id}_0"),
        InlineKeyboardButton("🃏", callback_data=f"card_{game_id}_{user_id}_1"),
        InlineKeyboardButton("🃏", callback_data=f"card_{game_id}_{user_id}_2"),
        InlineKeyboardButton("🃏", callback_data=f"card_{game_id}_{user_id}_3")
    ]]

    await message.reply_photo(
        photo="https://i.ibb.co/9ZcW4vR/cards-game.jpg",  # you can replace with your own image
        caption="🃏 4 cards are here!\n3 are 💥 bombs and 1 is 🐥 chick.\nChoose wisely!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Handle card pick
@app.on_callback_query(filters.regex(r'card_(\S+)_(\d+)_(\d+)'))
async def handle_card_pick(client: Client, callback_query):
    data = callback_query.data.split("_")
    game_id, user_id, choice = data[1], int(data[2]), int(data[3])
    picker_id = callback_query.from_user.id

    if picker_id != user_id:
        await callback_query.answer("This is not your game!", show_alert=True)
        return

    if user_id not in card_games or card_games[user_id]["game_id"] != game_id:
        await callback_query.answer("Game expired or invalid!", show_alert=True)
        return

    chick_index = card_games[user_id]["chick_index"]
    del card_games[user_id]  # End game after one pick

    if choice == chick_index:
        # Win 🐥 → random character from allowed rarities
        rarity = random.choice(RARITIES)

        pipeline = [
            {"$match": {
                "rarity": rarity,
                "img_url": {"$exists": True, "$ne": ""},
                "id": {"$exists": True},
                "name": {"$exists": True, "$ne": ""},
                "anime": {"$exists": True, "$ne": ""}
            }},
            {"$sample": {"size": 1}}
        ]

        cursor = collection.aggregate(pipeline)
        characters = await cursor.to_list(length=None)

        if characters:
            char = characters[0]
            await callback_query.message.reply_photo(
                photo=char["img_url"],
                caption=(
                    f"🎉 <b>You found the 🐥 chick!</b>\n\n"
                    f"🌸 <b>Name:</b> {char['name']}\n"
                    f"⛩️ <b>Team:</b> {char['anime']}\n"
                    f"🐾 <b>Rarity:</b> {char['rarity']}\n"
                    f"🆔 <b>ID:</b> {char['id']}"
                ),
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await callback_query.message.edit_text("🐥 You won, but no characters available right now!")
    else:
        await callback_query.message.edit_text("💥 Boom! You picked a bomb card. Better luck next time!")