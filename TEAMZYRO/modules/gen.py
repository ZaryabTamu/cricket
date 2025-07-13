import random
import string
from pymongo import ReturnDocument
from pyrogram import Client, filters
from pyrogram import enums
from TEAMZYRO import ZYRO as app
from TEAMZYRO import collection, user_collection, db, require_power

redeem_collection = db["redeem_codes"]  # Collection for redeem codes

# Command to generate a redeem code
@app.on_message(filters.command("cgen"))
@require_power("VIP")
async def generate_redeem_code(client, message):
    args = message.command
    if len(args) < 3:
        await message.reply_text("Usage: `/cgen <character_id> <redeem_limit>`", parse_mode=enums.ParseMode.MARKDOWN)
        return

    character_id = args[1]
    try:
        redeem_limit = int(args[2])
    except ValueError:
        await message.reply_text("Invalid redeem limit. It must be a number.", parse_mode=enums.ParseMode.MARKDOWN)
        return

    # Check if character exists
    character = await collection.find_one({'id': character_id})
    if not character:
        await message.reply_text("❌ Character not found.", parse_mode=enums.ParseMode.MARKDOWN)
        return

    # Generate a unique redeem code
    redeem_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Save redeem code in the database
    await redeem_collection.insert_one({
        "code": redeem_code,
        "character_id": character_id,
        "character_name": character["name"],
        "redeem_limit": redeem_limit,
        "redeemed_by": []
    })

    # Formatting message properly
    char_info = (
        f"🎭 *Character:* `{character['name']}`\n"
        f"📺 *Anime:* `{character.get('anime', 'Unknown')}`\n"
        f"🌟 *Rarity:* `{character.get('rarity', 'Unknown')}`\n"
        f"🖼 *Image:* [Click Here]({character.get('img_url', '#' )})\n\n"
        f"🔢 *Redeem Limit:* `{redeem_limit}`\n"
        f"🎟 *Redeem Code:* `{redeem_code}`"
    )

    await message.reply_text(f"✅ *Redeem code generated!*\n\n{char_info}", 
                             parse_mode=enums.ParseMode.MARKDOWN, 
                             disable_web_page_preview=True)


import random
import string
import time
from pyrogram import Client, filters
from pyrogram import enums

spam = {}

# Command to generate a daily redeem code for coins
@app.on_message(filters.command("dailycode"))
async def daily_code(client, message):
    """
    Generates a unique, single-use redeem code for a random amount of coins.
    Users are limited to generating one code every 24 hours.
    """
    user_id = message.from_user.id
    current_time = time.time()

    # Spam prevention: Check if the user has requested a code in the last 24 hours
    if user_id in spam and current_time - spam[user_id] < 86400:  # 86400 seconds = 24 hours
        remaining_time = int(86400 - (current_time - spam[user_id]))
        hours, remainder = divmod(remaining_time, 3600)
        minutes, _ = divmod(remainder, 60)
        await message.reply_text(
            f"⏳ You can only generate a daily code once every 24 hours. "
            f"Please wait {hours}h {minutes}m.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return

    # Generate a unique 8-character redeem code
    redeem_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Generate a random coin amount between 400 and 2000
    coin_amount = random.randint(400, 2000)

    # Save the new redeem code to the database
    await redeem_collection.insert_one({
        "code": redeem_code,
        "coin_amount": coin_amount,
        "redeem_limit": 1,  # This is a single-use code
        "redeemed_by": []   # List of user IDs who have redeemed it
    })

    # Update the user's timestamp in the spam prevention dictionary
    spam[user_id] = current_time

    # Format the response message
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

# Command to redeem a code for a character or coins
@app.on_message(filters.command("redeem"))
async def redeem_character_or_coins(client, message):
    """
    Allows a user to redeem a code for either a character or coins.
    Checks if the code is valid, not expired, and hasn't been used by the user.
    """
    if len(message.command) < 2:
        await message.reply_text("Usage: `/redeem <code>`", parse_mode=enums.ParseMode.MARKDOWN)
        return

    redeem_code = message.command[1]
    user_id = message.from_user.id

    # A little April Fool's joke
    if redeem_code == "1APRGIFT":
        await message.reply_text("🤣 Aap pagal ban chuke ho! Happy April Fool! 🎉", parse_mode=enums.ParseMode.MARKDOWN)
        return

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

    # Case 1: The code is for a character
    if "character_id" in redeem_data:
        # NOTE: Assumes 'collection' is your characters collection
        character = await collection.find_one({'id': redeem_data["character_id"]})
        if not character:
            await message.reply_text("❌ Character associated with this code not found.", parse_mode=enums.ParseMode.MARKDOWN)
            return

        # Add the character to the user's collection
        await user_collection.update_one(
            {'id': user_id},
            {'$push': {'characters': character}},
            upsert=True
        )

        char_info = (
            f"🎉 **You have successfully redeemed a character!**\n\n"
            f"🎭 **Character:** `{character['name']}`\n"
            f"📺 **Anime:** `{character.get('anime', 'N/A')}`\n"
            f"🌟 **Rarity:** `{character.get('rarity', 'N/A')}`\n"
            f"🖼 **Image:** [Click Here]({character.get('img_url', '#')})"
        )

        await message.reply_text(
            char_info,
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=False # Allow image preview for characters
        )

    # Case 2: The code is for coins
    elif "coin_amount" in redeem_data:
        coin_amount = redeem_data["coin_amount"]
        
        # Add the coins to the user's balance
        await user_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': coin_amount}},
            upsert=True
        )

        coin_info = (
            f"🎉 **Success!**\n\n"
            f"💰 You have successfully redeemed `{coin_amount}` coins!"
        )

        await message.reply_text(
            coin_info,
            parse_mode=enums.ParseMode.MARKDOWN
        )

    # Finally, update the redeem code's status to show this user has redeemed it
    await redeem_collection.update_one(
        {"code": redeem_code},
        {"$push": {"redeemed_by": user_id}}
    )
