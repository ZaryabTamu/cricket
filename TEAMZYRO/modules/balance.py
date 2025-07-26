from TEAMZYRO import *
from pyrogram import Client, filters
from pyrogram.types import Message, User
CallbackQuery
import html
import asyncio

# In-memory DB (replace with actual DB in production)
USER_DB = {}

def get_user_data(user_id):
    return USER_DB.setdefault(user_id, {"balance": 0, "coin": 0})

def update_user_data(user_id, data):
    USER_DB[user_id] = data

def extract_user_id(message: Message):
    # Priority: replied user > /command <user_id|username>
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    elif len(message.command) >= 2:
        return message.command[1]
    else:
        return message.from_user.id  # fallback to self

@Client.on_message(filters.command(["balance", "bal", "acc", "account", "wallet", "accountbal"]))
async def show_balance(client: Client, message: Message):
    user_input = None
    target_user = None

    # Get user: replied, argument, or self
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) >= 2:
        user_input = message.command[1]
        try:
            if user_input.startswith("@"):
                user_input = user_input[1:]
            target_user = await client.get_users(user_input)
        except Exception:
            return await message.reply_text("❌ User not found.")
    else:
        target_user = message.from_user

    user_data = get_user_data(target_user.id)
    name = html.escape(target_user.first_name)

    text = (
        f"**{name}**'s Profile\n"
        f"Balance : 💲 {user_data['balance']}\n"
        f"Coin : 🪙 {user_data['coin']}"
    )

    await message.reply_text(text)



@app.on_message(filters.command("pay"))
async def pay(client: Client, message: Message):
    sender = message.from_user
    sender_id = sender.id
    args = message.command

    if len(args) < 2:
        await message.reply_text("Usage: /pay <amount> [@username/user_id] [reason if amount > 20000] or reply to a user.")
        return

    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("Invalid amount. Please enter a positive number.")
        return

    # Identify recipient
    recipient = None
    if message.reply_to_message:
        recipient = message.reply_to_message.from_user
    elif len(args) > 2:
        try:
            if args[2].startswith("@"):
                recipient = await client.get_users(args[2])
            else:
                recipient = await client.get_users(int(args[2]))
        except Exception:
            return await message.reply_text("❌ Recipient not found. Use @username, ID or reply.")

    if not recipient:
        return await message.reply_text("❌ Recipient not found. Reply or use @username/ID.")

    recipient_id = recipient.id
    recipient_name = html.escape(recipient.first_name or str(recipient.id))
    sender_name = html.escape(sender.first_name or str(sender.id))

    if sender_id == recipient_id:
        return await message.reply_text("You cannot pay yourself.")

    # Owner can pay unlimited
    if sender_id == OWNER_ID:
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}}, upsert=True)
        _, rec_tokens = await get_balance(recipient_id, recipient_name)
        await message.reply_text(f"✅ You gifted {amount} coins to {recipient_name} (as owner).")
        await client.send_message(
            recipient_id,
            f"🎁 {sender_name} sent you {amount} coins.\n💰 Your New Balance: {amount:,} coins"
        )
        return

    sender_balance, _ = await get_balance(sender_id, sender_name)
    if sender_balance < amount:
        return await message.reply_text("🚫 You don’t have enough balance.")

    # If amount <= 20k, proceed instantly
    if amount <= 20000:
        await user_collection.update_one({'id': sender_id}, {'$inc': {'balance': -amount}})
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}}, upsert=True)

        updated_sender_balance, _ = await get_balance(sender_id, sender_name)
        updated_recipient_balance, _ = await get_balance(recipient_id, recipient_name)

        await message.reply_text(
            f"✅ You paid {amount:,} coins to {recipient_name}.\n"
            f"💰 Your New Balance: {updated_sender_balance:,} coins"
        )
        await client.send_message(
            recipient_id,
            f"🎉 You received {amount:,} coins from {sender_name}!\n"
            f"💰 Your New Balance: {updated_recipient_balance:,} coins"
        )
        return

    # If amount > 20k, ask reason
    reason = " ".join(args[3:]) if len(args) > 3 else None
    if not reason:
        return await message.reply_text("❗ You must provide a reason for large payments.\nUsage:\n`/pay 30000 @user For event prize`", parse_mode="markdown")

    # Send request to OWNER
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{sender_id}_{recipient_id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{sender_id}_{recipient_id}_{amount}")
        ]
    ])
    await client.send_message(
        OWNER_ID,
        f"💸 <b>Payment Request</b>\n\n"
        f"👤 From: <a href='tg://user?id={sender_id}'>{sender_name}</a>\n"
        f"➡ To: <a href='tg://user?id={recipient_id}'>{recipient_name}</a>\n"
        f"💰 Amount: <b>{amount:,}</b> coins\n"
        f"📝 Reason: <i>{html.escape(reason)}</i>",
        reply_markup=keyboard,
        parse_mode="html"
    )
    await message.reply_text("📨 Payment request sent to the owner for approval.")
@app.on_callback_query(filters.regex(r"^(approve|reject)_(\d+)_(\d+)_(\d+)$"))
async def handle_approval(client: Client, query: CallbackQuery):
    action, sender_id, recipient_id, amount = query.data.split("_")
    sender_id = int(sender_id)
    recipient_id = int(recipient_id)
    amount = int(amount)

    sender_user = await client.get_users(sender_id)
    recipient_user = await client.get_users(recipient_id)

    sender_name = html.escape(sender_user.first_name or str(sender_id))
    recipient_name = html.escape(recipient_user.first_name or str(recipient_id))

    if query.from_user.id != OWNER_ID:
        return await query.answer("Only owner can approve/decline.", show_alert=True)

    if action == "approve":
        sender_balance, _ = await get_balance(sender_id, sender_name)
        if sender_balance < amount:
            await client.send_message(sender_id, "🚫 Your balance dropped. Payment can't be processed.")
            return await query.message.edit_text("❌ Payment failed: sender has insufficient balance.")

        # Transfer
        await user_collection.update_one({'id': sender_id}, {'$inc': {'balance': -amount}})
        await user_collection.update_one({'id': recipient_id}, {'$inc': {'balance': amount}}, upsert=True)

        new_sender_balance, _ = await get_balance(sender_id, sender_name)
        new_recipient_balance, _ = await get_balance(recipient_id, recipient_name)

        await client.send_message(sender_id, f"✅ Your payment of {amount:,} coins to {recipient_name} was approved.\n💰 New Balance: {new_sender_balance:,} coins")
        await client.send_message(recipient_id, f"🎉 You received {amount:,} coins from {sender_name} (approved by owner).\n💰 New Balance: {new_recipient_balance:,} coins")

        await query.message.edit_text("✅ Payment Approved and completed.")
    else:
        await client.send_message(sender_id, "❌ Your payment was rejected by the owner. Reason was not valid or acceptable.\nPlease try again later.")
        await query.message.edit_text("❌ Payment request has been declined.")


@app.on_message(filters.command("redeemtoken"))
async def redeem_token(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command

    if len(args) < 2:
        await message.reply_text("Usage: /redeemtoken <amount>")
        return

    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError("Amount must be a positive number.")
        if amount % 1000 != 0:
            raise ValueError("Amount must be a multiple of 1000 (e.g., 1000, 2000, 3000).")
    except ValueError as e:
        error_message = str(e) if "multiple of 1000" in str(e) else "Invalid amount. Please enter a valid number."
        await message.reply_text(error_message)
        return

    user_balance, user_tokens = await get_balance(user_id)
    if user_balance < amount:
        await message.reply_text("Insufficient coin balance to redeem tokens.")
        return

    tokens_to_add = amount // 1000  # Calculate number of tokens (1 token per 1000 coins)
    await user_collection.update_one(
        {'id': user_id},
        {'$inc': {'balance': -amount, 'tokens': tokens_to_add}}
    )

    updated_balance, updated_tokens = await get_balance(user_id)
    await message.reply_text(
        f"✅ Successfully redeemed {tokens_to_add} token(s) for {amount} coins.\n"
        f"💰 New Balance: {updated_balance} coins\n"
        f"🎟 New Tokens: {updated_tokens}"
    )

@app.on_message(filters.command("kill"))
@require_power("VIP")
async def kill_handler(client, message):
    # Get the user_id from the reply message
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        await message.reply_text("Please reply to a user's message to use the /kill command.")
        return

    command_args = message.text.split()

    if len(command_args) < 2:
        await message.reply_text("Please specify an option: `c` to delete character, `f` to delete full data, or `b` to delete balance.")
        return

    option = command_args[1]

    try:
        if option == 'f':
            # Delete full user data
            await user_collection.delete_one({"id": user_id})
            await message.reply_text("The full data of the user has been deleted.")

        elif option == 'c':
            # Delete specific character from the user's collection
            if len(command_args) < 3:
                await message.reply_text("Please specify a character ID to remove.")
                return

            char_id = command_args[2]
            user = await user_collection.find_one({"id": user_id})

            if user and 'characters' in user:
                characters = user['characters']
                updated_characters = [c for c in characters if c.get('id') != char_id]

                if len(updated_characters) == len(characters):
                    await message.reply_text(f"No character with ID {char_id} found in the user's collection.")
                    return

                # Update user collection
                await user_collection.update_one({"id": user_id}, {"$set": {"characters": updated_characters}})
                await message.reply_text(f"Character with ID {char_id} has been removed from the user's collection.")
            else:
                await message.reply_text(f"No characters found in the user's collection.")

        elif option == 'b':
            # Check if amount is provided
            if len(command_args) < 3:
                await message.reply_text("Please specify an amount to deduct from balance.")
                return

            try:
                amount = int(command_args[2])
            except ValueError:
                await message.reply_text("Invalid amount. Please enter a valid number.")
                return

            # Fetch user balance
            user_data = await user_collection.find_one({"id": user_id}, {"balance": 1})
            if user_data and "balance" in user_data:
                current_balance = user_data["balance"]
                new_balance = max(0, current_balance - amount)  # Ensure balance doesn't go negative
                
                await user_collection.update_one({"id": user_id}, {"$set": {"balance": new_balance}})
                await message.reply_text(f"{amount} has been deducted from the user's balance. New balance: {new_balance}")
            else:
                await message.reply_text("The user has no balance to deduct from.")

        else:
            await message.reply_text("Invalid option. Use `c` for character, `f` for full data, or `b {amount}` to deduct balance.")

    except Exception as e:
        print(f"Error in /kill command: {e}")
        await message.reply_text("An error occurred while processing the request. Please try again later.")
