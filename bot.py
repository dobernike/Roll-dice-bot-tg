import os
import re
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# e.g. 2d6, 1d20, 4d6+3, 2d8-1
DICE_PATTERN = re.compile(
    r"^(\d+)d(\d+)([+-]\d+)?$",
    re.IGNORECASE,
)

MAX_DICE = 100
MAX_SIDES = 10_000


def parse_roll(text: str):
    """Parse NdN[+/-M] and return (count, sides, modifier) or raise ValueError."""
    text = text.strip().replace(" ", "")
    m = DICE_PATTERN.match(text)
    if not m:
        raise ValueError(f"Invalid dice format: {text!r}")
    count = int(m.group(1))
    sides = int(m.group(2))
    modifier = int(m.group(3)) if m.group(3) else 0
    if count < 1 or count > MAX_DICE:
        raise ValueError(f"Dice count must be 1–{MAX_DICE}.")
    if sides < 2 or sides > MAX_SIDES:
        raise ValueError(f"Sides must be 2–{MAX_SIDES}.")
    return count, sides, modifier


def format_result(
    name: str,
    expr: str,
    count: int,
    sides: int,
    modifier: int,
    rolls: list[int],
) -> str:
    total = sum(rolls) + modifier
    roll_str = ", ".join(str(r) for r in rolls)

    lines = [f"🎲 *{name}* rolls *{expr}*"]

    if count > 1:
        lines.append(f"Rolls: [{roll_str}]")

    # Critical hit/fail only applies to a single d20 roll
    if count == 1 and sides == 20 and modifier == 0:
        if rolls[0] == 20:
            lines.append(f"🌟 *CRITICAL HIT!* → *{total}*")
        elif rolls[0] == 1:
            lines.append(f"💀 *CRITICAL FAIL!* → *{total}*")
        else:
            lines.append(f"Result: *{total}*")
    else:
        mod_str = ""
        if modifier > 0:
            mod_str = f" + {modifier}"
        elif modifier < 0:
            mod_str = f" - {abs(modifier)}"
        lines.append(f"Result: *{total}*{mod_str and f' ({roll_str}{mod_str})'}")

    return "\n".join(lines)


DND_DICE = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]


def dice_keyboard() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(d, callback_data=f"roll:1{d}") for d in DND_DICE]
    # Two rows: 4 + 3
    return InlineKeyboardMarkup([buttons[:4], buttons[4:]])


async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.full_name or user.username or "Someone"

    if not context.args:
        await update.message.reply_text(
            f"🎲 *{name}*, pick a die:",
            reply_markup=dice_keyboard(),
            parse_mode="Markdown",
        )
        return

    expr = context.args[0]
    try:
        count, sides, modifier = parse_roll(expr)
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}\nExample: /roll 2d6+3")
        return

    rolls = [random.randint(1, sides) for _ in range(count)]
    text = format_result(name, expr, count, sides, modifier, rolls)
    await update.message.reply_text(text, parse_mode="Markdown")


async def dice_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("roll:"):
        return

    expr = query.data[len("roll:"):]
    user = query.from_user
    name = user.full_name or user.username or "Someone"

    try:
        count, sides, modifier = parse_roll(expr)
    except ValueError as e:
        await query.edit_message_text(f"⚠️ {e}")
        return

    rolls = [random.randint(1, sides) for _ in range(count)]
    text = format_result(name, expr, count, sides, modifier, rolls)
    await query.edit_message_text(text, parse_mode="Markdown")


HELP_TEXT = (
    "🎲 *Dice Bot — Help*\n\n"
    "*Command:*\n"
    "`/roll <NdN[+/-M]>`\n\n"
    "*Examples:*\n"
    "• `/roll 1d20` — roll a 20-sided die\n"
    "• `/roll 4d6` — roll four 6-sided dice\n"
    "• `/roll 2d8+3` — roll two d8s and add 3\n"
    "• `/roll 1d100` — percentile roll\n\n"
    "*Special rules:*\n"
    "• 🌟 Natural 20 on a single d20 → *Critical Hit*\n"
    "• 💀 Natural 1 on a single d20 → *Critical Fail*\n\n"
    f"*Limits:* up to 100 dice, up to 10,000 sides."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎲 *Dice Bot* is ready!\n\n" + HELP_TEXT,
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable not set.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CallbackQueryHandler(dice_button, pattern=r"^roll:"))

    logger.info("Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
