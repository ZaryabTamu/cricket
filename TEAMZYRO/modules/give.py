from pyrogram import filters
from TEAMZYRO import app, sudo_users, user_collection, require_power

# Power required: "give_coin"
@require_power("give_coin")
@app.on_message(filters.command("givec") & filters.reply)
async def give_coins(_, message):
    try:
        # Command format: /givec 1000 (must be replying to user)
        amount = int(message.text.split()[1])
        if amount <= 0:
            return await message.reply_text("❌ Please enter a valid positive number of coins.")

        user_id = message.reply_to_message.from_user.id

        # Check if user exists, if not create
        user = await user_collection.find_one({"id": user_id})
        if not user:
            await user_collection.insert_one({
                "id": user_id,
                "balance": amount,
                "tokens": 0,
                "characters": [],
            })
        else:
            await user_collection.update_one({"id": user_id}, {"$inc": {"balance": amount}})

        await message.reply_text(f"✅ Successfully added {amount} coins to the user `{user_id}`.")
    except (IndexError, ValueError):
        await message.reply_text("❌ Correct usage: /givec {amount} (reply to a user)")
