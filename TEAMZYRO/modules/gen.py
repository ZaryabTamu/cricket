import random
import string
import time
from pyrogram import Client, filters
from pyrogram import enums

# --- Assumed Initializations ---
# These variables are assumed to be initialized in your main bot file.
from TEAMZYRO import ZYRO as app
from TEAMZYRO import collection, user_collection, db, require_power
# ---------------------------------

redeem_collection = db["redeem_codes"]  # Collection for redeem codes

# --- In-memory Locks ---
# These sets keep track of users currently processing a command
# to prevent spam and race conditions. They reset on bot restart.
processing_redeems = set()
processing_dailycode = set()


@app.on_message(filters.command("cgen"))
@require_power("VIP")
async def generate_redeem_code(client, message):
    """
    Generates a redeem code for a specific character. (Admin/VIP command)
    Usage: /cgen <character_id> <redeem_limit>
    """
    args = message.command
    if len(args) < 3:
        await message.reply_text("Usage: `/cgen <character_id> <redeem_limit>`", parse_mode=enums.ParseMode.MARKDOWN)
        return

    character_id = args[1]
    try:
        redeem_limit = int(args[2])
        if redeem_limit <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Invalid redeem limit. It must be a positive number.", parse_mode=enums.ParseMode.MARKDOWN)
        return

    # Check if character exists in the main character collection
    character = await collection.find_one({'id': character_id})
    if not character:
        await message.reply_text("❌ Character not found.", parse_mode=enums.ParseMode.MARKDOWN)
        return

    # Generate a unique 8-character redeem code
    redeem_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Save the new redeem code to the database
    await redeem_collection.insert_one({
        "code": redeem_code,
        "character_id": character_id,
        "character_name": character["name"],
        "redeem_limit": redeem_limit,
        "redeemed_by": []
    })

    # Format the response message
    char_info = (
        f"🎭 **Character:** `{character['name']}`\n"
        f"📺 **Team:** `{character.get('anime', 'N/A')}`\n"
        f"🌟 **Rarity:** `{character.get('rarity', 'N/A')}`\n"
        f"🖼 **Image:** [Click Here]({character.get('img_url', '#')})\n\n"
        f"🔢 **Redeem Limit:** `{redeem_limit}`\n"
        f"🎟 **Redeem Code:** `{redeem_code}`"
    )

    await message.reply_text(
        f"✅ **Redeem code generated!**\n\n{char_info}",
        parse_mode=enums.ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@app.on_message(filters.command("dailycode"))
async def daily_code(client, message):
    """
    Generates a daily redeem code for coins with a 24-hour cooldown,
    stored persistently in the database. Includes a lock to prevent spamming.
    """
    user_id = message.from_user.id
    
    # --- Command Lock ---
    if user_id in processing_dailycode:
        await message.reply_text("⏳ Please wait, your previous request is still being processed.", parse_mode=enums.ParseMode.MARKDOWN)
        return
    
    processing_dailycode.add(user_id)
    try:
        current_time = time.time()
        
        # --- Persistent Cooldown Check (MongoDB) ---
        user_data = await user_collection.find_one({'id': user_id})
        last_code_time = user_data.get('last_daily_code_time', 0) if user_data else 0

        if current_time - last_code_time < 86400:  # 86400 seconds = 24 hours
            remaining_time = int(86400 - (current_time - last_code_time))
            hours, remainder = divmod(remaining_time, 3600)
            minutes, _ = divmod(remainder, 60)
            await message.reply_text(
                f"⏳ You have already claimed your daily code. "
                f"Please wait **{hours}h {minutes}m** for the next one.",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            return

        # Generate a unique 8-character redeem code
        redeem_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        coin_amount = random.randint(400, 2000)

        # Save the new redeem code to the database
        await redeem_collection.insert_one({
            "code": redeem_code,
            "coin_amount": coin_amount,
            "redeem_limit": 1,
            "redeemed_by": []
        })

        # Update User's Cooldown Time in MongoDB
        await user_collection.update_one(
            {'id': user_id},
            {'$set': {'last_daily_code_time': current_time}},
            upsert=True
        )

        code_info = (
            f"🎟 **Daily Redeem Code Generated!**\n\n"
            f"💰 **Coins:** `{coin_amount}`\n"
            f"🎟 **Redeem Code:** `{redeem_code}`\n\n"
            f"Use `/redeem {redeem_code}` to claim your coins!"
        )

        await message.reply_text(
            code_info,
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

    finally:
        # --- Release Lock ---
        processing_dailycode.remove(user_id)


@app.on_message(filters.command("redeem"))
async def redeem_character_or_coins(client, message):
    """
    Allows a user to redeem a code for a character or coins.
    Includes a lock to prevent spamming and race conditions.
    """
    user_id = message.from_user.id

    # --- Command Lock ---
    if user_id in processing_redeems:
        await message.reply_text("⏳ Please wait, your previous request is still being processed.", parse_mode=enums.ParseMode.MARKDOWN)
        return
    
    processing_redeems.add(user_id)
    try:
        if len(message.command) < 2:
            await message.reply_text("Usage: `/redeem <code>`", parse_mode=enums.ParseMode.MARKDOWN)
            return

        redeem_code = message.command[1]

        # Find the redeem code in the database
        redeem_data = await redeem_collection.find_one({"code": redeem_code})
        if not redeem_data:
            await message.reply_text("❌ Invalid or expired redeem code.", parse_mode=enums.ParseMode.MARKDOWN)
            return

        # Check if the user has already redeemed this specific code
        if user_id in redeem_data.get("redeemed_by", []):
            await message.reply_text("❌ You have already redeemed this code.", parse_mode=enums.ParseMode.MARKDOWN)
            return

        # Check if the code has reached its redemption limit
        if len(redeem_data.get("redeemed_by", [])) >= redeem_data.get("redeem_limit", 1):
            await message.reply_text("❌ This redeem code has reached its usage limit.", parse_mode=enums.ParseMode.MARKDOWN)
            return

        # --- Redemption Logic ---
        if "character_id" in redeem_data:
            character = await collection.find_one({'id': redeem_data["character_id"]})
            if not character:
                await message.reply_text("❌ Character associated with this code not found.", parse_mode=enums.ParseMode.MARKDOWN)
                return
            await user_collection.update_one({'id': user_id}, {'$push': {'characters': character}}, upsert=True)
            char_info = (
                f"🎉 **You have successfully redeemed a character!**\n\n"
                f"🎭 **Character:** `{character['name']}`\n"
                f"🖼 **Image:** [Click Here]({character.get('img_url', '#')})"
            )
            await message.reply_text(char_info, parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=False)
        elif "coin_amount" in redeem_data:
            coin_amount = redeem_data["coin_amount"]
            await user_collection.update_one({'id': user_id}, {'$inc': {'balance': coin_amount}}, upsert=True)
            await message.reply_text(f"🎉 **Success!** You have redeemed `{coin_amount}` coins!", parse_mode=enums.ParseMode.MARKDOWN)

        # Update the redeem code's status
        await redeem_collection.update_one({"code": redeem_code}, {"$push": {"redeemed_by": user_id}})

    finally:
        # --- Release Lock ---
        processing_redeems.remove(user_id)
