import html
from typing import Optional, List

import telegram.ext as tg
from telegram import Message, Chat, Update, Bot, ParseMode, User, MessageEntity
from telegram import TelegramError
from telegram.error import BadRequest
from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import mention_html

import tg_bot.modules.sql.locks_sql as sql
from tg_bot import dispatcher, SUDO_USERS, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import can_delete, is_user_admin, user_not_admin, user_admin, \
    bot_can_delete, is_bot_admin
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import users_sql

LOCK_TYPES = {'استیکر': Filters.sticker,
              'آهنگ': Filters.audio,
              'صدا': Filters.voice,
              'فایل': Filters.document & ~Filters.animation,
              'فیلم': Filters.video,
              'ویدیو': Filters.video_note,
              'مخاطب': Filters.contact,
              'عکس': Filters.photo,
              'گیف': Filters.animation,
              'لینک': Filters.entity(MessageEntity.URL) | Filters.caption_entity(MessageEntity.URL),
              'ربات': Filters.status_update.new_chat_members,
              'فوروارد': Filters.forwarded,
              'بازی': Filters.game,
              'مکان': Filters.location,
			  'sticker': Filters.sticker,
              'audio': Filters.audio,
              'voice': Filters.voice,
              'document': Filters.document & ~Filters.animation,
              'video': Filters.video,
              'videonote': Filters.video_note,
              'contact': Filters.contact,
              'photo': Filters.photo,
              'gif': Filters.animation,
              'url': Filters.entity(MessageEntity.URL) | Filters.caption_entity(MessageEntity.URL),
              'bots': Filters.status_update.new_chat_members,
              'forward': Filters.forwarded,
              'game': Filters.game,
              'location': Filters.location,
              }

GIF = Filters.animation
OTHER = Filters.game | Filters.sticker | GIF 
MEDIA = Filters.audio | Filters.document | Filters.video | Filters.video_note | Filters.voice | Filters.photo
MESSAGES = Filters.text | Filters.contact | Filters.location | Filters.venue | Filters.command 
PREVIEWS = Filters.entity("url")

RESTRICTION_TYPES = {'پیام': MESSAGES,
                     'مدیا': MEDIA,
                     'دیگر': OTHER,
                       #'پیشنمایش': PREVIEWS, # NOTE: this has been removed cos its useless atm.
                     'گروه': Filters.all
					 'messages': MESSAGES,
                     'media': MEDIA,
                     'other': OTHER,
                       #'پیشنمایش': PREVIEWS, # NOTE: this has been removed cos its useless atm.
                     'gp': Filters.all}

PERM_GROUP = 1
REST_GROUP = 2


class CustomCommandHandler(tg.CommandHandler):
    def __init__(self, command, callback, **kwargs):
        super().__init__(command, callback, **kwargs)

    def check_update(self, update):
        return super().check_update(update) and not (
                sql.is_restr_locked(update.effective_chat.id, 'messages') and not is_user_admin(update.effective_chat,
                                                                                                update.effective_user.id))


tg.CommandHandler = CustomCommandHandler


# NOT ASYNC
def restr_members(bot, chat_id, members, messages=False, media=False, other=False, previews=False):
    for mem in members:
        if mem.user in SUDO_USERS:
            pass
        try:
            bot.restrict_chat_member(chat_id, mem.user,
                                     can_send_messages=messages,
                                     can_send_media_messages=media,
                                     can_send_other_messages=other,
                                     can_add_web_page_previews=previews)
        except TelegramError:
            pass


# NOT ASYNC
def unrestr_members(bot, chat_id, members, messages=True, media=True, other=True, previews=True):
    for mem in members:
        try:
            bot.restrict_chat_member(chat_id, mem.user,
                                     can_send_messages=messages,
                                     can_send_media_messages=media,
                                     can_send_other_messages=other,
                                     can_add_web_page_previews=previews)
        except TelegramError:
            pass


@run_async
def locktypes(bot: Bot, update: Update):
    update.effective_message.reply_text("\n - ".join(["قفل ها: "] + list(LOCK_TYPES) + list(RESTRICTION_TYPES)))


@user_admin
@bot_can_delete
@loggable
def lock(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    if can_delete(chat, bot.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=True)
                message.reply_text("{} برای افراد عادی قفل شد".format(args[0]))

                return "<b>{}:</b>" \
                       "\n#قفل" \
                       "\n<b>توسط:</b> {}" \
                       "\nبخش <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=True)
                if args[0] == "previews":
                    members = users_sql.get_chat_members(str(chat.id))
                    restr_members(bot, chat.id, members, messages=True, media=True, other=True)

                message.reply_text("{} برای افراد عادی قفل شد!".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#قفل" \
                       "\n<b>توسط:</b> {}" \
                       "\nبخش <code>{}</code>.".format(html.escape(chat.title),
                                                          mention_html(user.id, user.first_name), args[0])

            else:
                message.reply_text("چیو میخوای قفل کنی ؟ لیست قفل هارو با !قفلها یا /locktypes نشون میدم")

    else:
        message.reply_text("اومم من هنوز ادمین نیستم ! شایدم اجازه قفل برام فعال نیس")

    return ""


@run_async
@user_admin
@loggable
def unlock(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    if is_user_admin(chat, message.from_user.id):
        if len(args) >= 1:
            if args[0] in LOCK_TYPES:
                sql.update_lock(chat.id, args[0], locked=False)
                message.reply_text("{}برای همه باز شد!".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#بی_قفل" \
                       "\n<b>توسط:</b> {}" \
                       "\nبخش <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])

            elif args[0] in RESTRICTION_TYPES:
                sql.update_restriction(chat.id, args[0], locked=False)
                """
                members = users_sql.get_chat_members(chat.id)
                if args[0] == "messages":
                    unrestr_members(bot, chat.id, members, media=False, other=False, previews=False)

                elif args[0] == "media":
                    unrestr_members(bot, chat.id, members, other=False, previews=False)

                elif args[0] == "other":
                    unrestr_members(bot, chat.id, members, previews=False)

                elif args[0] == "previews":
                    unrestr_members(bot, chat.id, members)

                elif args[0] == "all":
                    unrestr_members(bot, chat.id, members, True, True, True, True)
                """
                message.reply_text("قفل {} برداشته شد!!".format(args[0]))

                return "<b>{}:</b>" \
                       "\n#بی_قفل" \
                       "\n<b>توسط:</b> {}" \
                       "\nبخش <code>{}</code>.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name), args[0])
            else:
                message.reply_text("چیو میخوای باز کنی؟ از دستور !قفلها یا /locktypes لیست بخش هامو ببین")

        else:
            bot.sendMessage(chat.id, "چیو میخوای باز کنی ؟ ")

    return ""


@run_async
@user_not_admin
def del_lockables(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    for lockable, filter in LOCK_TYPES.items():
        if filter(message) and sql.is_locked(chat.id, lockable) and can_delete(chat, bot.id):
            if lockable == "ربات":
                new_members = update.effective_message.new_chat_members
                for new_mem in new_members:
                    if new_mem.is_bot:
                        if not is_bot_admin(chat, bot.id):
                            message.reply_text("اگه کسی رباتی بیاره من اجازه ادد کردن بهش نمیدم ولی "
                                               "هنوز ادمین نیستم!")
                            return

                        chat.kick_member(new_mem.id)
                        
            else:
                try:
                    message.delete()
                except BadRequest as excp:
                    if excp.message == "Message to delete not found":
                        pass
                    else:
                        LOGGER.exception("ERROR in lockables")

            break


@run_async
@user_not_admin
def rest_handler(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    for restriction, filter in RESTRICTION_TYPES.items():
        if filter(msg) and sql.is_restr_locked(chat.id, restriction) and can_delete(chat, bot.id):
            try:
                msg.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("ERROR in restrictions")
            break


def build_lock_message(chat_id):
    locks = sql.get_locks(chat_id)
    restr = sql.get_restr(chat_id)
    if not (locks or restr):
        res = "قفل خاصی برای این گپ تنظیم نکردی"
    else:
        res = "اینا قفل های مربوط به این گپ هستن!:"
        if locks:
            res += "\n - استیکر = `{}`" \
                   "\n - آهنگ = `{}`" \
                   "\n - صدا = `{}`" \
                   "\n - فایل = `{}`" \
                   "\n - فیلم = `{}`" \
                   "\n - پیام ویدیویی = `{}`" \
                   "\n - مخاطب = `{}`" \
                   "\n - عکس = `{}`" \
                   "\n - گیف = `{}`" \
                   "\n - لینک = `{}`" \
                   "\n - ربات = `{}`" \
                   "\n - فوروارد = `{}`" \
                   "\n - بازی = `{}`" \
                   "\n - مکان = `{}`".format(locks.sticker, locks.audio, locks.voice, locks.document,
                                                 locks.video, locks.videonote, locks.contact, locks.photo, locks.gif, locks.url,
                                                 locks.bots, locks.forward, locks.game, locks.location)
        if restr:
            res += "\n - پیام = `{}`" \
                   "\n - مدیا = `{}`" \
                   "\n - دیگر = `{}`" \
                   "\n - پیشنمایش = `{}`" \
                   "\n - همه = `{}`".format(restr.messages, restr.media, restr.other, restr.preview,
                                            all([restr.messages, restr.media, restr.other, restr.preview]))
    return res


@run_async
@user_admin
def list_locks(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    res = build_lock_message(chat.id)

    update.effective_message.reply_text(res, parse_mode=ParseMode.MARKDOWN)

    
def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return build_lock_message(chat_id)


__help__ = """
 میگن گپتو قفل کن 
 تهمت تب چی بودن به کسی نزن🤣

- [!قفلها] 
[/locktypes] 👉 لیست قفل ها
———————————————————--
*فقط ادمین ها*
- [!قفل] (نام_بخش)
[/lock] (LockName) 👉 قفل بخش
———————————————————--
- [!بازکردن] (نام_بخش)
[/unlock] (LockName) 👉 بازکردن بخش
———————————————————--
- [!وضعیت] 
[/locks] 👉 وضعیت قفل ها
"""

__mod_name__ = "قفل🔐"

LOCKTYPES_HANDLER = DisableAbleCommandHandler(["قفلها", "locktypes"], locktypes)
LOCK_HANDLER = CommandHandler(["قفل", "lock"], lock, pass_args=True, filters=Filters.group)
UNLOCK_HANDLER = CommandHandler(["بازکردن", "unlock"], unlock, pass_args=True, filters=Filters.group)
LOCKED_HANDLER = CommandHandler(["وضعیت", "locks"], list_locks, filters=Filters.group)

dispatcher.add_handler(LOCK_HANDLER)
dispatcher.add_handler(UNLOCK_HANDLER)
dispatcher.add_handler(LOCKTYPES_HANDLER)
dispatcher.add_handler(LOCKED_HANDLER)

dispatcher.add_handler(MessageHandler(Filters.all & Filters.group, del_lockables), PERM_GROUP)
dispatcher.add_handler(MessageHandler(Filters.all & Filters.group, rest_handler), REST_GROUP)
