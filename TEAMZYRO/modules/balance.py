from TEAMZYRO import *
from pyrogram import Client, filters
from pyrogram.types import Message
import html

async def get_balance(user_id):
    user_data = await user_collection.find_one({'id': user_id}, {'balance': 1, 'tokens': 1})
    if user_data:
        return user_data.get('balance', 0), user_data.get('tokens', 0)
    return 0, 0

@app.on_message(filters.command("balance"))
async def balance(client: Client, message: Message):
    user_id = message.from_user.id
    user_balance, user_tokens = await get_balance(user_id)

    response = (
        f"👤 **{html.escape(message.from_user.first_name)}'s Profile**\n\n"
        f"💲 **Money:** {user_balance}\n"
        f"🎫 **Tokens:** {user_tokens}"
    )

    await message.reply_text(response, quote=True)

@app.on_message(filters.command("pay"))
async def pay(client: Client, message: Message):
    sender_id = message.from_user.id
    args = message.command

    # If no amount provided
    if len(args) < 2:
        await message.reply_text(
            "⚠️ **Usage:** `/pay <amount> [@username/user_id]` or reply to a user.\n\n"
            "💡 Example: `/pay 100 @username`"
        )
        return

    # Validate amount
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Invalid amount. Please enter a positive number.")
        return

    recipient_id = None
    recipient_name = None

    # If replying to a user
    if message.reply_to_message:
        recipient_id = message.reply_to_message.from_user.id
        recipient_name = message.reply_to_message.from_user.first_name

    # If username/user_id provided
    elif len(args) > 2:
        try:
            recipient_id = int(args[2])
        except ValueError:
            recipient_username = args[2].lstrip('@')  # remove '@'
            user_data = await user_collection.find_one(
                {'username': recipient_username}, {'id': 1, 'first_name': 1}
            )
            if user_data:
                recipient_id = user_data['id']
                recipient_name = user_data.get('first_name', recipient_username)
            else:
                await message.reply_text("🙅 Recipient not found. Please reply to a user or provide a valid username/ID.")
                return

    if not recipient_id:
        await message.reply_text("⚠️ Recipient not found. Reply to a user or provide a valid user ID/username.")
        return

    # Check sender balance
    sender_balance, _ = await get_balance(sender_id)
    if sender_balance < amount:
        await message.reply_text("💸 Insufficient balance! You don’t have enough coins.")
        return

    # Update balances
    await user_collection.update_one({'id': sender_id}, {'$inc': {'balance': -amount}})
    await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}})

    updated_sender_balance, _ = await get_balance(sender_id)
    updated_recipient_balance, _ = await get_balance(recipient_id)

    # Display names
    recipient_display = html.escape(recipient_name or str(recipient_id))
    sender_display = html.escape(message.from_user.first_name or str(sender_id))

    # Notify sender
    await message.reply_text(
        f"✅ **Payment Successful!**\n\n"
        f"👤 You sent **{amount} 💰 coins** to **{recipient_display}**.\n"
        f"💳 **Your New Balance:** {updated_sender_balance} coins"
    )

    # Notify recipient
    await client.send_message(
        chat_id=recipient_id,
        text=(
            f"🎉 **You Received a Payment!**\n\n"
            f"💸 **Amount:** {amount} coins\n"
            f"👤 **From:** {sender_display}\n"
            f"💳 **Your New Balance:** {updated_recipient_balance} coins"
        )
    )

@app.on_message(filters.command("kill"))
@require_power("VIP")
async def kill_handler(client, message):
    # Check if command is used as a reply
    if not message.reply_to_message:
        await message.reply_text("⚠️ Please **reply** to a user's message to use the `/kill` command.")
        return

    user_id = message.reply_to_message.from_user.id
    command_args = message.text.split()

    if len(command_args) < 2:
        await message.reply_text(
            "📌 **Usage:** `/kill <option>`\n\n"
            "🔹 `c <character_id>` — Remove a character from the user.\n"
            "🔹 `f` — Delete the **entire user data**.\n"
            "🔹 `b <amount>` — Deduct coins from balance.\n\n"
            "💡 Example:\n"
            "`/kill c 01`\n"
            "`/kill f`\n"
            "`/kill b 100`"
        )
        return

    option = command_args[1]

    try:
        # 🔥 Delete FULL user data
        if option == 'f':
            await user_collection.delete_one({"id": user_id})
            await message.reply_text(
                f"💀 **Full Wipe Executed!**\n\n"
                f"🧹 All data for user [`{user_id}`] has been **completely deleted** from the database."
            )

        # 🎭 Delete a specific character
        elif option == 'c':
            if len(command_args) < 3:
                await message.reply_text("⚠️ Please specify a **character ID** to remove.\n\nExample: `/kill c 01`")
                return

            char_id = command_args[2]
            user = await user_collection.find_one({"id": user_id})

            if user and 'characters' in user:
                characters = user['characters']
                updated_characters = [c for c in characters if c.get('id') != char_id]

                if len(updated_characters) == len(characters):
                    await message.reply_text(f"❌ No character with ID `{char_id}` found in this user's collection.")
                    return

                # Update user collection
                await user_collection.update_one({"id": user_id}, {"$set": {"characters": updated_characters}})
                await message.reply_text(
                    f"🗡 **Character Removed!**\n\n"
                    f"🆔 Character ID: `{char_id}`\n"
                    f"👤 User ID: `{user_id}`\n\n"
                    f"✅ Successfully deleted from their collection."
                )
            else:
                await message.reply_text("📭 This user has **no characters** in their collection.")

        # 💰 Deduct balance
        elif option == 'b':
            if len(command_args) < 3:
                await message.reply_text("⚠️ Please specify an **amount** to deduct.\n\nExample: `/kill b 100`")
                return

            try:
                amount = int(command_args[2])
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ Invalid amount. Please enter a **positive number**.")
                return

            # Fetch user balance
            user_data = await user_collection.find_one({"id": user_id}, {"balance": 1})
            if user_data and "balance" in user_data:
                current_balance = user_data["balance"]
                new_balance = max(0, current_balance - amount)  # Prevent negative balance

                await user_collection.update_one({"id": user_id}, {"$set": {"balance": new_balance}})
                await message.reply_text(
                    f"💸 **Balance Deduction Successful!**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"➖ Deducted: `{amount}` coins\n"
                    f"💰 New Balance: `{new_balance}` coins"
                )
            else:
                await message.reply_text("💰 This user has **no balance** to deduct from.")

        # ❌ Invalid option
        else:
            await message.reply_text(
                "❌ Invalid option.\n\n"
                "📌 **Valid Options:**\n"
                "🔹 `c <character_id>` — Remove a character\n"
                "🔹 `f` — Delete full user data\n"
                "🔹 `b <amount>` — Deduct coins"
            )

    except Exception as e:
        print(f"Error in /kill command: {e}")
        await message.reply_text("⚠️ An unexpected error occurred while processing the request. Please try again later.")



@app.on_message(filters.command("give"))
@require_power("VIP")  # Only VIPs can use this
async def give_handler(client: Client, message: Message):
    # Must reply to a user
    if not message.reply_to_message:
        await message.reply_text("⚠️ Please **reply** to a user's message to give them coins or tokens.")
        return

    args = message.command
    if len(args) < 3:
        await message.reply_text(
            "📌 **Usage:** `/give <option> <amount>`\n\n"
            "🔹 `c <amount>` — Give coins 💰\n"
            "🔹 `t <amount>` — Give tokens 🎫\n\n"
            "💡 Example:\n"
            "`/give c 100`\n"
            "`/give t 5`"
        )
        return

    option = args[1].lower()

    # Validate amount
    try:
        amount = int(args[2])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Invalid amount. Please enter a **positive number**.")
        return

    # Get recipient details
    recipient_id = message.reply_to_message.from_user.id
    recipient_name = html.escape(message.reply_to_message.from_user.first_name or str(recipient_id))

    if option == 'c':
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}})
        await message.reply_text(
            f"💰 **Coins Added!**\n\n"
            f"👤 User: {recipient_name}\n"
            f"➕ Amount: `{amount}` coins\n"
            f"✅ Successfully credited to their balance."
        )

        await client.send_message(
            chat_id=recipient_id,
            text=(
                f"🎉 **You Received Coins!**\n\n"
                f"💰 Amount: `{amount}` coins\n"
                f"👤 From: {html.escape(message.from_user.first_name)}"
            )
        )

    elif option == 't':
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'tokens': amount}})
        await message.reply_text(
            f"🎫 **Tokens Added!**\n\n"
            f"👤 User: {recipient_name}\n"
            f"➕ Amount: `{amount}` tokens\n"
            f"✅ Successfully credited to their account."
        )

        await client.send_message(
            chat_id=recipient_id,
            text=(
                f"🎉 **You Received Tokens!**\n\n"
                f"🎫 Amount: `{amount}` tokens\n"
                f"👤 From: {html.escape(message.from_user.first_name)}"
            )
        )

    else:
        await message.reply_text(
            "❌ Invalid option.\n\n"
            "📌 Use:\n"
            "🔹 `c` = Coins 💰\n"
            "🔹 `t` = Tokens 🎫"
        )

@app.on_message(filters.command("redeemtoken"))
async def redeem_token(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command

    TOKEN_RATE = 1000  # 💰 1000 coins = 🎟 1 token

    # ✅ Step 1: Check arguments
    if len(args) < 2:
        await message.reply_text(
            "📌 **Usage:** `/redeemtoken <amount>`\n\n"
            f"💲 **Rate:** {TOKEN_RATE} coins = 🎟 1 Token\n\n"
            "💡 Examples:\n"
            f"`/redeemtoken {TOKEN_RATE}` → 🎟 1 Token\n"
            f"`/redeemtoken {TOKEN_RATE * 3}` → 🎟 3 Tokens"
        )
        return

    # ✅ Step 2: Validate amount
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError("Amount must be a positive number.")
        if amount % TOKEN_RATE != 0:
            raise ValueError(f"Amount must be a multiple of {TOKEN_RATE} (e.g., {TOKEN_RATE}, {TOKEN_RATE*2}, {TOKEN_RATE*3}).")
    except ValueError as e:
        error_message = (
            str(e)
            if "multiple" in str(e)
            else "❌ Invalid amount. Please enter a valid number."
        )
        await message.reply_text(
            f"{error_message}\n\n"
            f"💲 **Rate:** {TOKEN_RATE} coins = 🎟 1 Token"
        )
        return

    # ✅ Step 3: Check user balance
    user_balance, user_tokens = await get_balance(user_id)
    if user_balance < amount:
        await message.reply_text(
            f"❌ You don’t have enough coins!\n\n"
            f"💰 Your Balance: {user_balance} coins\n"
            f"🔒 Required: {amount} coins\n\n"
            f"💲 **Rate:** {TOKEN_RATE} coins = 🎟 1 Token"
        )
        return

    # ✅ Step 4: Calculate tokens
    tokens_to_add = amount // TOKEN_RATE

    # ✅ Step 5: Update DB
    await user_collection.update_one(
        {'id': user_id},
        {'$inc': {'balance': -amount, 'tokens': tokens_to_add}}
    )

    # ✅ Step 6: Send confirmation
    updated_balance, updated_tokens = await get_balance(user_id)
    await message.reply_text(
        f"🎉 **Redeem Successful!**\n\n"
        f"🔁 You exchanged: `{amount}` coins → 🎟 `{tokens_to_add}` token(s)\n\n"
        f"💲 **Rate:** {TOKEN_RATE} coins = 🎟 1 Token\n\n"
        f"💰 New Balance: `{updated_balance}` coins\n"
        f"🎟 New Tokens: `{updated_tokens}`"
    )