import os
import logging
import io
import aiohttp
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ACTION, TYPING_PROMPT = range(2)

# User data storage
user_data = {}
user_limits = {}

# --- Helper Functions ---

async def generate_image(prompt: str, style: str = "default") -> bytes:
    """Generate an image using Pollinations.ai"""
    try:
        # Format the prompt
        formatted_prompt = prompt.replace(" ", "%20")
        
        # Style modifiers
        style_modifiers = {
            "default": "",
            "anime": "anime+style",
            "realistic": "photorealistic",
            "cartoon": "cartoon+style",
            "painting": "oil+painting",
            "sketch": "pencil+sketch",
            "cyberpunk": "cyberpunk+style",
            "fantasy": "fantasy+art"
        }
        
        style_mod = style_modifiers.get(style, "")
        
        # Build the URL
        if style_mod and style != "default":
            full_prompt = f"{formatted_prompt}%2C+{style_mod}"
        else:
            full_prompt = formatted_prompt
        
        url = f"{POLLINATIONS_API}{full_prompt}?width=1024&height=1024&nologo=true"
        
        logger.info(f"Generating image for: {prompt} (style: {style})")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"API error: {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None

async def check_user_limit(user_id: int) -> bool:
    """Check if user has reached daily limit (5 images per day)"""
    today = datetime.now().date()
    if user_id not in user_limits:
        user_limits[user_id] = {"count": 0, "date": today}
        return True
    
    if user_limits[user_id]["date"] != today:
        user_limits[user_id] = {"count": 0, "date": today}
        return True
    
    return user_limits[user_id]["count"] < 5

async def increment_user_count(user_id: int):
    """Increment user's generation count"""
    today = datetime.now().date()
    if user_id not in user_limits or user_limits[user_id]["date"] != today:
        user_limits[user_id] = {"count": 1, "date": today}
    else:
        user_limits[user_id]["count"] += 1

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued"""
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("🎨 Generate Image", callback_data="generate")],
        [InlineKeyboardButton("🎭 Change Style", callback_data="style")],
        [InlineKeyboardButton("📊 My Usage", callback_data="usage")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"🎨 Welcome {user.first_name} to Easy Image Generator!\n\n"
        f"I can create images from your text descriptions using AI.\n\n"
        f"✨ **Features:**\n"
        f"• Free unlimited generation\n"
        f"• 8 different art styles\n"
        f"• High-quality 1024x1024 images\n"
        f"• 5 images per day (free limit)\n\n"
        f"Select an option below to get started:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    return SELECTING_ACTION

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "generate":
        await query.edit_message_text(
            "🎨 **Describe the image you want:**\n\n"
            "Be specific for better results!\n\n"
            "Example: 'A beautiful sunset over a mountain lake with pine trees'\n\n"
            "Send your description:"
        )
        return TYPING_PROMPT
    
    elif data == "style":
        keyboard = [
            [InlineKeyboardButton("🎨 Default", callback_data="style_default")],
            [InlineKeyboardButton("🌸 Anime", callback_data="style_anime")],
            [InlineKeyboardButton("📸 Realistic", callback_data="style_realistic")],
            [InlineKeyboardButton("🎭 Cartoon", callback_data="style_cartoon")],
            [InlineKeyboardButton("🖼️ Painting", callback_data="style_painting")],
            [InlineKeyboardButton("✏️ Sketch", callback_data="style_sketch")],
            [InlineKeyboardButton("💜 Cyberpunk", callback_data="style_cyberpunk")],
            [InlineKeyboardButton("🐉 Fantasy", callback_data="style_fantasy")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎭 **Choose an art style:**",
            reply_markup=reply_markup
        )
        return SELECTING_ACTION
    
    elif data == "usage":
        today = datetime.now().date()
        if user_id in user_limits and user_limits[user_id]["date"] == today:
            count = user_limits[user_id]["count"]
            remaining = 5 - count
        else:
            count = 0
            remaining = 5
        
        await query.edit_message_text(
            f"📊 **Your Usage Report**\n\n"
            f"📅 Today: {today.strftime('%B %d, %Y')}\n"
            f"🎨 Images generated: {count}/5\n"
            f"✅ Remaining: {remaining}\n\n"
            f"⏰ Resets at midnight UTC"
        )
        return SELECTING_ACTION
    
    elif data == "help":
        help_text = (
            "ℹ️ **How to use this bot:**\n\n"
            "1️⃣ Click 'Generate Image'\n"
            "2️⃣ Describe what you want\n"
            "3️⃣ Wait a few seconds!\n\n"
            "**Commands:**\n"
            "/start - Show main menu\n"
            "/generate - Generate an image\n"
            "/style - Change art style\n"
            "/usage - Check your usage\n"
            "/cancel - Cancel current operation"
        )
        await query.edit_message_text(help_text)
        return SELECTING_ACTION
    
    return SELECTING_ACTION

async def style_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle style selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    style = query.data.replace("style_", "")
    
    # Store selected style
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["style"] = style
    
    await query.edit_message_text(
        f"✅ Style set to: **{style.capitalize()}**\n\n"
        f"Now describe the image you want to generate:"
    )
    return TYPING_PROMPT

async def receive_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive prompt and generate image"""
    user_id = update.effective_user.id
    prompt = update.message.text
    
    # Check daily limit
    if not await check_user_limit(user_id):
        await update.message.reply_text(
            "⚠️ **Daily limit reached!**\n\n"
            f"You've used all 5 free generations today.\n"
            f"Please try again tomorrow.\n\n"
            f"Use /usage to check your stats."
        )
        return ConversationHandler.END
    
    # Get user's selected style
    style = user_data.get(user_id, {}).get("style", "default")
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"🎨 **Generating your image...**\n\n"
        f"📝 Prompt: {prompt}\n"
        f"🎭 Style: {style.capitalize()}\n\n"
        f"⏳ Please wait a few seconds..."
    )
    
    # Generate the image
    image_data = await generate_image(prompt, style)
    
    if image_data:
        # Increment usage count
        await increment_user_count(user_id)
        
        # Send the image
        await update.message.reply_photo(
            photo=io.BytesIO(image_data),
            caption=(
                f"✅ **Image Generated!**\n\n"
                f"📝 {prompt}\n"
                f"🎭 Style: {style.capitalize()}\n\n"
                f"📊 You have {5 - user_limits[user_id]['count']} generations remaining today\n\n"
                f"Use /generate to create another image!"
            )
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    else:
        await processing_msg.edit_text(
            "❌ **Failed to generate image**\n\n"
            "Please try again with a different prompt."
        )
    
    # Clean up user data
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /generate command"""
    await update.message.reply_text(
        "🎨 **Describe the image you want:**\n\n"
        "Be specific! Example: 'A magical forest with glowing mushrooms'"
    )
    return TYPING_PROMPT

async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /style command"""
    keyboard = [
        [InlineKeyboardButton("🎨 Default", callback_data="style_default")],
        [InlineKeyboardButton("🌸 Anime", callback_data="style_anime")],
        [InlineKeyboardButton("📸 Realistic", callback_data="style_realistic")],
        [InlineKeyboardButton("🎭 Cartoon", callback_data="style_cartoon")],
        [InlineKeyboardButton("🖼️ Painting", callback_data="style_painting")],
        [InlineKeyboardButton("✏️ Sketch", callback_data="style_sketch")],
        [InlineKeyboardButton("💜 Cyberpunk", callback_data="style_cyberpunk")],
        [InlineKeyboardButton("🐉 Fantasy", callback_data="style_fantasy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎭 **Choose your preferred art style:**",
        reply_markup=reply_markup
    )
    return SELECTING_ACTION

async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /usage command"""
    user_id = update.effective_user.id
    today = datetime.now().date()
    
    if user_id in user_limits and user_limits[user_id]["date"] == today:
        count = user_limits[user_id]["count"]
        remaining = 5 - count
    else:
        count = 0
        remaining = 5
    
    await update.message.reply_text(
        f"📊 **Your Usage Report**\n\n"
        f"📅 Today: {today.strftime('%B %d, %Y')}\n"
        f"🎨 Images generated today: {count}/5\n"
        f"✅ Remaining: {remaining}\n\n"
        f"⏰ Resets at midnight UTC"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text(
        "❌ **Operation cancelled.**\n\n"
        "Use /start to begin again!"
    )
    return ConversationHandler.END

# --- Error Handler ---

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.warning(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text(
            "⚠️ **Something went wrong.**\n\n"
            "Please try again later or use /start to restart."
        )

# --- Main Function ---

def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in environment variables!")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('generate', generate_command),
            CommandHandler('style', style_command),
        ],
        states={
            SELECTING_ACTION: [
                CallbackQueryHandler(button_callback, pattern="^(generate|style|usage|help)$"),
                CallbackQueryHandler(style_selection, pattern="^style_"),
            ],
            TYPING_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prompt),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start),
        ],
        allow_reentry=True,
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("usage", usage_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🚀 Easy Image Generator Bot is starting...")
    logger.info("🤖 Bot username: @easy_image_generator_0bot")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
