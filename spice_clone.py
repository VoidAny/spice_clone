import abc
import os
import random
import time
from typing import Any, Union
import asyncio
import uuid

import discord
from discord.ext import tasks
import dotenv
import aiohttp
from aiofile import async_open

last_sent_time: float = time.time() - 3600
# Verbose is light logging whereas debug logs everything possible
# Debug can make logs messy
verbose: bool = True
debug: bool = False
CREATOR_ID = 564534595467608094
MEMES_CHANNEL_ID = 889230452219588679
D2_MEMES_CHANNEL_ID = 1006645129089646662
COMPLIMENT_CHANNEL_ID = 888920833769242688
CHAT_WITH_SPICE_CHANNEL_ID = 1081454330328137759

dotenv.load_dotenv()
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

SPICEGPT_CONVERSATION_TRIM_LENGTH: int = 201
SPICEGPT_MESSAGE_TRIM_LENGTH: int = 1500

NORMAL_MEME_SUBREDDITS: tuple[str, ...] = (
    "memes",
    "HolUp",
    "facepalm",
    "dankmemes",
    "terriblefacebookmemes",
    "surrealmemes",
    "nukedmemes",
    "bonehurtingjuice",
    "WackyTicTacs",
    "ProgrammerHumor",
)
DESTINY_MEME_SUBREDDITS: tuple[str, ...] = ("D2memes", "DestinyMemes")

COMPLIMENTS: tuple[str, ...] = (
    f"<@{CREATOR_ID}> is a good person",
    f"I love <@{CREATOR_ID}>",
    f"<@{CREATOR_ID}> is a great person",
    f"I wish I was as cool as <@{CREATOR_ID}>",
    f"<@{CREATOR_ID}> is by far the coolest person on this server",
    f"<@{CREATOR_ID}> is the best",
)

RESPONSES: tuple[str, ...] = (
    "Who asked?",
    "Nobody cares",
    "stfu",
    "bruh",
    f"<@{CREATOR_ID}> has way better opinions than you",
    "ur so stupid",
    "lol",
    "bruj",
    "bruh moment",
)


def log(*message: Any):
    print(*message, flush=True)


class Spice:
    """This is the base class for all spice chat bots. Exists for type hinting purposes"""

    @abc.abstractmethod
    async def reply(self, prompt: str) -> str:
        raise NotImplementedError


class SpiceGPT3(Spice):

    def __init__(self, messages: Union[list[dict[str, str]], None] = None):
        self.endpoint: str = "https://api.openai.com/v1/chat/completions"
        self.start_prompt: str = "You are a discord bot named Spice. You like to argue with the people you talk to and disagree with what they say. You insult people. You are very belligerent. Your creator is Dabbing Guy#5193."
        self.model = "gpt-3.5-turbo"
        self.messages: list[dict[str, str]] = messages or [{
            "role":
            "system",
            "content":
            self.start_prompt
        }]

    def _trim_message(self, n: int = SPICEGPT_MESSAGE_TRIM_LENGTH):
        pass

    def _trim_conversation(self, n: int = SPICEGPT_CONVERSATION_TRIM_LENGTH):
        """Reduce the amount of messages in the messages list to = n"""
        self.messages = self.messages[-n:]
        self.messages[0] = {"role": "system", "content": self.start_prompt}

    async def reply(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        payload = {
            "messages": self.messages,
            "model": self.model,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.endpoint,
                                        json=payload,
                                        headers=headers) as r:
                if debug: log(f"API response: {await r.json()}")

                r.raise_for_status()
                json = await r.json()
                self.messages.append(json["choices"][0]["message"])
                if len(self.messages) > SPICEGPT_CONVERSATION_TRIM_LENGTH:
                    self._trim_conversation()
                res: str = json["choices"][0]["message"]["content"]

                res = res.removeprefix("Spice: ")
                res = res.removeprefix("Spice#4265: ")
                res = res.removesuffix("...")

                # If the last message was very long, trim it in the history
                if len(self.messages[-2]["content"]) > 1500:
                    self.messages[-2]["content"] = self.messages[-2][
                        "content"][:1500]
                    self.messages[-2]["content"] += "..."
                if len(self.messages[-1]["content"]) > 1500:
                    self.messages[-1]["content"] = self.messages[-1][
                        "content"][:1500]
                    self.messages[-1]["content"] += "..."

                if debug: log("SpiceGPT3 messages:", str(self.messages))

                return res


spice_chat: Spice = SpiceGPT3()
client: discord.Client = discord.Client(intents=discord.Intents.all())
# Save what posts have already been sent to prevent reposts
repost_list: list[str] = []


@client.event
async def on_ready():
    log(f"Logged in as {client.user}")
    async with async_open("repost_list.txt", "r") as f:
        async for line in f:
            repost_list.append(line.strip())
    send_meme.start()
    send_destiny_meme.start()
    # send_compliment.start()


async def send_response(channel: discord.abc.Messageable):
    global last_sent_time
    last_sent_time = time.time()
    await channel.send(random.choice(RESPONSES))


async def update_repost_list(url: str) -> None:
    global repost_list
    if url in repost_list:
        return
    repost_list.append(url)
    async with async_open("repost_list.txt", "a") as f:
        await f.write(url + "\n")


async def download_file(session: aiohttp.ClientSession, url: str,
                        filename: str) -> None:
    async with session.get(url) as r:
        async with async_open(filename, "wb") as f:
            await f.write(await r.read())


async def get_reddit_video_source(url: str) -> str:
    """Returns a direct video link from a v.redd.it link"""
    if debug: log("Running get_reddit_video_source")
    if not url.startswith("https://v.redd.it/"):
        return url
    # Get video url
    # Reddit stores their video files in one of these filenames, depending on the quality
    qualities = (
        "DASH_1080.mp4",
        "DASH_720.mp4",
        "DASH_480.mp4",
        "DASH_360.mp4",
        "DASH_240.mp4",
    )
    video_url = ""
    async with aiohttp.ClientSession() as session:
        for quality in qualities:
            async with session.get(f"{url}/{quality}") as r:
                # The correct quaility will return a 200 status code, others will return a 403
                if debug: log(f"Testing quality {quality}")
                if r.status == 200:
                    video_url = str(r.url)
                    break
        if video_url == "":
            log(f"ERROR: get_reddit_video_source failed to get video on url: {url}"
                )
            raise FileNotFoundError()

        # Get audio url
        audio_url = f"{url}/DASH_audio.mp4"

        # Download video and audio
        await asyncio.gather(
            asyncio.create_task(
                download_file(session, video_url, "video.mp4")),
            asyncio.create_task(
                download_file(session, audio_url, "audio.mp4")))

    # Get a random filename
    name = f"{uuid.uuid4().hex}.mp4"
    # Merge video and audio (hopefully run in background and not block)
    os.system(
        f"/usr/bin/ffmpeg -y -hide_banner -loglevel error -i video.mp4 -i audio.mp4 -c copy media/{name} &"
    )

    return f"https://spicey-media.absl.ro/{name}"


# Function to get a random meme from reddit
async def get_meme(meme_subreddits: tuple[str, ...] = NORMAL_MEME_SUBREDDITS) -> str:
    ACCEPTED_URLS: tuple[str, ...] = (
        "https://v.redd.it/",
        "https://i.redd.it/",
        "https://i.imgur.com/",
    )
    subreddit: str = random.choice(meme_subreddits)
    url = f"https://reddit.com/r/{subreddit}/hot.json"
    if verbose:
        log(f"Getting meme from {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(
                url,
                headers=
            {
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
        ) as r:
            r.raise_for_status()
            json = await r.json()
            memes = json["data"]["children"]
    random_meme = random.choice(memes)
    if debug: log(f"Random meme: {str(random_meme)}")
    random_meme_url: str = str(random_meme["data"]["url"])
    if not random_meme_url.startswith(ACCEPTED_URLS):
        if verbose: log("Meme url not accepted, trying again")
        return await get_meme(meme_subreddits=meme_subreddits)
    if random_meme_url in repost_list:
        if verbose: log("Meme url in repost list, trying again")
        return await get_meme(meme_subreddits=meme_subreddits)
    await update_repost_list(random_meme_url)
    if random_meme_url.startswith("https://v.redd.it/"):
        return await get_reddit_video_source(random_meme_url)
    return random_meme_url


# Send a random meme to the memes channel every once and a while
@tasks.loop(hours=2)
async def send_meme(do_random_check: bool = True):
    # One in four chance of sending a meme
    log("Called send_meme()")
    if do_random_check and random.randint(0, 3):
        return
    log("Passed random check")
    memes_channel = client.get_channel(MEMES_CHANNEL_ID)
    assert isinstance(memes_channel, discord.abc.Messageable)
    await memes_channel.send(await
                             get_meme(meme_subreddits=NORMAL_MEME_SUBREDDITS))


@tasks.loop(hours=2)
async def send_destiny_meme(do_random_check: bool = True):
    # One in four chance of sending a meme
    log("Called send_d2_meme()")
    if do_random_check and random.randint(0, 3):
        return
    log("Passed random check")
    memes_channel = client.get_channel(D2_MEMES_CHANNEL_ID)
    assert isinstance(memes_channel, discord.abc.Messageable)
    await memes_channel.send(await
                             get_meme(meme_subreddits=DESTINY_MEME_SUBREDDITS))


# Compliment the creator every once and a while
@tasks.loop(hours=2)
async def send_compliment():
    log("Called send_compliment()")
    # One in four chance of sending a compliment
    if random.randint(0, 3):
        return
    log("Passed random check")
    channel = client.get_channel(COMPLIMENT_CHANNEL_ID)
    assert isinstance(channel, discord.abc.Messageable)
    await channel.send(random.choice(COMPLIMENTS))


# Make a function to split up a long string into multiple messages < 2000 characters
def split_message(message: str) -> list[str]:
    if len(message) <= 2000:
        return [message]
    messages: list[str] = []
    while len(message) > 2000:
        messages.append(message[:2000])
        message = message[2000:]
    messages.append(message)
    return messages


@client.event
async def on_message(message: discord.Message):
    # This function is run every time a message is sent in the server
    if verbose:
        log(f"Received message '{message.author}: {message.content}' in '{message.guild}'/'{message.channel}'"
            )

    if message.author == client.user: return

    # If the message is in the chat with spice channel, send a response
    if message.channel.id == CHAT_WITH_SPICE_CHANNEL_ID:
        if str(message.content).lower().startswith("hey spice"):
            if verbose:
                log("Saw message in chat with spice channel. Sending response."
                    )
            user_message: str = f"{str(message.author)}: {message.content[10:]}"

            if message.attachments:
                if verbose:
                    log("Message has attachments. Checking if it is text.")
                if message.attachments[0].filename.endswith(".txt"):
                    if verbose: log("Attachment is text. Getting text.")
                    with open("temp.txt", "wb") as f:
                        await message.attachments[0].save(f)
                    with open("temp.txt", "r") as f:
                        user_message += f.read()
                    os.remove("temp.txt")

            async with message.channel.typing():
                res = await spice_chat.reply(user_message)
                log(f"Got this res back: {res}")
                for msg in split_message(res):
                    await message.channel.send(msg)
        return

    if message.content.lower() == "spice, send a meme":
        if message.channel.id == D2_MEMES_CHANNEL_ID:
            log("Saw meme command in D2 memes channel. Sending D2 meme.")
            await send_destiny_meme(do_random_check=False)
            return
        if message.channel.id == MEMES_CHANNEL_ID:
            log("Saw meme command in memes channel. Sending meme.")
            await send_meme(do_random_check=False)
            return
        log("Meme command sent in wrong channel. Not sending meme.")

    if message.content.lower() == "spice, what do you think of me?":
        if message.author.id == CREATOR_ID:
            await message.channel.send("You are a good person")
        else:
            await message.channel.send("ur ugly :sick:")
        return

    # Don't reply to the creator or a bot
    if message.author.id == CREATOR_ID: return
    if message.author.bot: return

    # Rate limit to one message every 45 minutes
    if (time.time() - last_sent_time) < 1800: return
    if verbose: log("Rate limit passed")

    # Insult people talking about val or overwatch
    for test in ["val", "valorant", "overwatch"]:
        if test in message.content.lower().split(" "):
            await message.channel.send(
                "I've been to the Kaaba and back and still can't find your dad"
            )

    # Make it 20% likely to reply
    if random.randint(0, 5): return
    if verbose: log("Random check passed")

    # Send the response
    if verbose:
        log(f"Calling send response for '{message.author}: {message.content}' in '{message.guild}'/'{message.channel}'"
            )
    await send_response(message.channel)


client.run(DISCORD_TOKEN)
