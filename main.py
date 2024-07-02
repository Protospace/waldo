import os, logging
DEBUG = os.environ.get('DEBUG')
logging.basicConfig(
        format='[%(asctime)s] %(levelname)s %(module)s/%(funcName)s - %(message)s',
        level=logging.DEBUG if DEBUG else logging.INFO)

from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from telethon import TelegramClient, events
from aiohttp import web
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import pytz

import settings

logging.getLogger('aiohttp').setLevel(logging.DEBUG if DEBUG else logging.WARNING)
logging.getLogger('twilio').setLevel(logging.DEBUG if DEBUG else logging.WARNING)

# TODO: use adjectives + animal? https://gist.github.com/xeoncross/5381806b18de1f395187
md5 = lambda x: hashlib.md5(x.encode()).hexdigest()[:4]

bot = TelegramClient('data/bot', settings.API_ID, settings.API_HASH).start(bot_token=settings.API_TOKEN)
twilio_client = Client(settings.TWILIO_SID, settings.TWILIO_TOKEN)
app = web.Application()

TIMEZONE_CALGARY = pytz.timezone('America/Edmonton')

try:
    data = json.load(open('data/data.json'))
except:
    logging.info('data.json missing, initializing data.')
    data = {}
if 'forwards' not in data: data['forwards'] = {}

def store_data():
    with open('data/data.json', 'w') as f:
        json.dump(data, f, indent=4)


@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply('This bot proxies Protospace questions to a support chat.')

@bot.on(events.NewMessage)
async def new_message(event):
    reply_id = event.message.reply_to_msg_id

    logging.info('=> Telegram - id: {}, reply_id: {}, sender: {} ({}), text: {}'.format(
        event.message.id, reply_id, event.sender.first_name, event.sender_id, event.raw_text
    ))

    if not reply_id:
        logging.info('    Not a reply, ignoring')
        return

    forward_key = str(reply_id) + str(event.chat_id)

    if forward_key not in data['forwards']:
        logging.info('    Not a Waldo forward reply, ignoring')
        return

    forward = data['forwards'][forward_key]

    logging.info('    Valid reply to: {} ({}), original: {}'.format(
        forward['alias'], forward['sms']['from'], forward['sms']['body']
    ))

    response = '{}: {}'.format(event.sender.first_name, event.raw_text)
    twilio_resp = twilio_client.messages.create(
        body=response,
        to=forward['sms']['from'],
        from_=forward['sms']['to'],
    )

    now = datetime.now(timezone.utc)

    reply = {
        'message_id': event.message.id,
        'chat_id': event.chat_id,
        'sender_id': event.sender_id,
        'name': event.sender.first_name,
        'text': event.raw_text,
        'time_utc': now.isoformat(),
        'time_yyc': now.astimezone(TIMEZONE_CALGARY).isoformat(),
    }

    forward['replies'].append(reply)
    store_data()

    if twilio_resp.error_message:
        logging.error('    Error: {} ({})'.format(twilio_resp.error_message, twilio_resp.error_code))
        await event.reply('Error: {} ({})'.format(twilio_resp.error_message, twilio_resp.error_code))
    else:
        logging.info('    Sent: "{}"'.format(response))
        await event.reply('Sent!')



async def index(request):
    return web.Response(text='Hello, world')

async def sms(request):
    post = await request.post()

    sms = {
        'smsmessagesid': post['SmsMessageSid'],
        'smssid': post['SmsSid'],
        'messagesid': post['MessageSid'],
        'smsstatus': post['SmsStatus'],
        'body': post['Body'],
        'to': post['To'],
        'from': post['From'],
    }

    alias = md5(sms['from'])
    message = '{}: {}'.format(alias, sms['body'])

    logging.info('<= SMS - smssid: {}, from: {} ({}), text: {}'.format(
        sms['smssid'], alias, sms['from'], sms['body'],
    ))

    forward = await bot.send_message(settings.WALDO_CHAT_ID, message)
    forward_key = str(forward.id) + str(settings.WALDO_CHAT_ID)

    now = datetime.now(timezone.utc)

    data['forwards'][forward_key] = dict(
        sms=sms,
        alias=alias,
        replies=[],
        time_utc=now.isoformat(),
        time_yyc=now.astimezone(TIMEZONE_CALGARY).isoformat(),
    )
    store_data()

    resp = MessagingResponse()
    return web.Response(body=str(resp), content_type='application/xml')

async def main():
    app.router.add_get('/', index)
    app.router.add_post('/sms', sms)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8083)
    await site.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main())

    bot.run_until_disconnected()
