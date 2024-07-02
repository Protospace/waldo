import os, logging
DEBUG = os.environ.get('DEBUG')
logging.basicConfig(
        format='[%(asctime)s] %(levelname)s %(module)s/%(funcName)s - %(message)s',
        level=logging.DEBUG if DEBUG else logging.INFO)

from twilio.twiml.messaging_response import MessagingResponse
from telethon import TelegramClient, events
from aiohttp import web
import asyncio
import hashlib
import json

import settings

# TODO: use adjectives + animal? https://gist.github.com/xeoncross/5381806b18de1f395187
md5 = lambda x: hashlib.md5(x.encode()).hexdigest()[:4]

bot = TelegramClient('data/bot', settings.API_ID, settings.API_HASH).start(bot_token=settings.API_TOKEN)
app = web.Application()

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
async def echo_all(event):
    await event.reply(event.text)

async def index(request):
    return web.Response(text='Hello, world')

async def sms(request):
    post = await request.post()
    print(post)

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

    forward = await bot.send_message(settings.WALDO_CHAT_ID, message)
    forward_key = str(forward.id) + str(settings.WALDO_CHAT_ID)

    data['forwards'][forward_key] = dict(sms=sms, alias=alias)
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
