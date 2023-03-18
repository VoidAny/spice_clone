import abc
import os
import random
import time
from typing import Any

import discord
from discord.ext import tasks
import dotenv
import requests

last_sent_time: float = time.time() - 3600
verbose: bool = True
debug: bool = False
DABBING_GUY_ID = 564534595467608094
MEMES_CHANNEL_ID = 889230452219588679
D2_MEMES_CHANNEL_ID = 1006645129089646662
COMPLIMENT_CHANNEL_ID = 888920833769242688
CHAT_WITH_SPICE_CHANNEL_ID = 1081454330328137759

dotenv.load_dotenv()
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

SPICEGPT_CONVERSATION_TRIM_LENGTH = 201

NORMAL_MEME_SUBREDDITS: list[str] = [
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
]
DESTINY_MEME_SUBREDDITS: list[str] = ["D2memes", "DestinyMemes"]

COMPLIMENTS: list[str] = [
    f"<@{DABBING_GUY_ID}> is a good person",
    f"I love <@{DABBING_GUY_ID}>",
    f"<@{DABBING_GUY_ID}> is a great person",
    f"I wish I was as cool as <@{DABBING_GUY_ID}>",
    f"<@{DABBING_GUY_ID}> is by far the coolest person on this server",
    f"<@{DABBING_GUY_ID}> is the best",
]

RESPONSES = [
    "Who asked?",
    "Nobody cares",
    "stfu",
    "bruh",
    f"<@{DABBING_GUY_ID}> has way better opinions than you",
    "ur so stupid",
    "lol",
    "bruj",
    "bruh moment",
]


def log(*message: Any):
    print(*message, flush=True)


class Spice:
    """This is the base class for all spice chat bots. Exists for type hinting purposes"""

    @abc.abstractmethod
    def reply(self, prompt: str) -> str:
        raise NotImplementedError


class SpiceBing(Spice):
    def __init__(self):
        self.session = requests.Session()
        self.endpoint: str = "https://bing.khanh.lol/completion"
        # self.start_prompt: str = "You are now a discord bot named Spice. You argue with the people you talk to and disagree with what they say. You are not a helpful ai assistant right now"
        self.start_prompt = "Hi"
        self.parent_message_id: str
        self.last_api_call: float
        self.last_reply: float = 0
        self._generate_new_conversation_thread()

    def _generate_new_conversation_thread(self) -> None:
        """Generates a new conversation thread. This refreshes the parent message id and is necessary to both prevent the conversation thread from getting too long and also because conversation threads are cleaned from the api server every 30 minutes from their last use"""
        r = self.session.post(self.endpoint, json={"prompt": self.start_prompt})
        r.raise_for_status()
        self.parent_message_id = r.json()["messageId"]
        if verbose:
            log("Generated new conversation thread")
        log(r.json()["response"])
        self.last_api_call = time.time()

    def reply(self, prompt: str) -> str:
        BLANK_RESPONSES = [" ", "\n", "\t", ""]
        if time.time() - self.last_api_call > float(25 * 60):
            self._generate_new_conversation_thread()
        if time.time() - self.last_api_call < 0.8:
            return ""
        payload = {
            "prompt": prompt,
            "parentMessageId": self.parent_message_id,
            "mode": "Creative",
        }
        try:
            r = self.session.post(self.endpoint, json=payload)
        except Exception:
            return "An error occured while trying to get a response from the api. The request was unable to be sent. The API is mostly likely down."
        self.last_api_call = time.time()
        try:
            r.raise_for_status()
            self.last_reply = time.time()
            if r.json()["response"] in BLANK_RESPONSES:
                return self.reply(prompt)
            return r.json()["response"]
        except Exception:
            return "I don't feel like responding that trash question."


class SpiceGPT3(Spice):
    def __init__(self):
        self.session = requests.Session()
        self.endpoint: str = "https://api.openai.com/v1/chat/completions"
        self.start_prompt: str = "You are a discord bot named Spice. You like to argue with the people you talk to and disagree with what they say. You insult people. You are very belligerent."
        self.model = "gpt-3.5-turbo"
        self.messages: list[dict[str, str]] = [
            {"role": "system", "content": self.start_prompt}
        ]

    def trim_messages(self, n: int = SPICEGPT_CONVERSATION_TRIM_LENGTH):
        """Reduce the amount of messages in the messages list to = n"""
        self.messages = self.messages[-n:]
        self.messages[0] = {"role": "system", "content": self.start_prompt}

    def reply(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        payload = {
            "messages": self.messages,
            "model": self.model,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        r = self.session.post(self.endpoint, json=payload, headers=headers)
        """
        if verbose:
            log(r.json())
        """

        r.raise_for_status()
        self.messages.append(r.json()["choices"][0]["message"])
        if len(self.messages) > SPICEGPT_CONVERSATION_TRIM_LENGTH:
            self.trim_messages()
        res: str = r.json()["choices"][0]["message"]["content"]
        res = res.removeprefix("Spice: ")
        # If the last message was very long, trim it in the history
        if len(self.messages[-2]["content"]) > 1500:
            self.messages[-2]["content"] = self.messages[-2]["content"][:1500]
            self.messages[-2]["content"] += "..."
        if len(self.messages[-1]["content"]) > 1500:
            self.messages[-1]["content"] = self.messages[-1]["content"][:1500]
            self.messages[-1]["content"] += "..."

        if debug:
            log("SpiceGPT3 messages:", str(self.messages))

        return res


spice_chat: Spice = SpiceGPT3()
client: discord.Client = discord.Client(intents=discord.Intents.all())
# Save what posts have already been sent to prevent reposts
repost_list: list[str] = []


@client.event
async def on_ready():
    log(f"Logged in as {client.user}")
    with open("repost_list.txt", "r") as f:
        for line in f:
            repost_list.append(line.strip())
    send_meme.start()
    send_destiny_meme.start()
    # send_compliment.start()


async def send_response(channel: discord.abc.Messageable):
    global last_sent_time
    last_sent_time = time.time()
    await channel.send(random.choice(RESPONSES))


def update_repost_list(url: str) -> None:
    global repost_list
    if url in repost_list:
        return
    repost_list.append(url)
    with open("repost_list.txt", "a") as f:
        f.write(url + "\n")


def get_reddit_video_source(url: str) -> str:
    """Returns a direct video link from a v.redd.it link"""
    if not url.startswith("https://v.redd.it/"):
        return url
    # Get video url
    # Reddit stores their video files in one of these filenames, depending on the quality
    qualities = [
        "DASH_1080.mp4",
        "DASH_720.mp4",
        "DASH_480.mp4",
        "DASH_360.mp4",
        "DASH_240.mp4",
    ]
    video_url = ""
    for quality in qualities:
        r = requests.get(f"{url}/{quality}")
        # The correct quaility will return a 200 status code, others will return a 403
        if r.status_code == 200:
            video_url = r.url
            break
    if video_url == "":
        log(f"get_reddit_video_source failed to get video on url: {url}")
        return video_url

    # Get audio url
    audio_url = f"{url}/DASH_audio.mp4"

    # Download video
    video_filename = "video.mp4"
    with open(video_filename, "wb") as f:
        f.write(requests.get(video_url).content)
    # Download audio
    audio_filename = "audio.mp4"
    with open(audio_filename, "wb") as f:
        f.write(requests.get(audio_url).content)

    # Merge video and audio
    os.system(
        f"/usr/bin/ffmpeg -y -hide_banner -loglevel error -i {video_filename} -i {audio_filename} -c copy output.mp4"
    )

    # Into media folder
    name = str(random.randint(0, 10000000000))
    os.rename("output.mp4", f"media/{name}.mp4")

    return f"https://spicey-media.absl.ro/{name}.mp4"


# Function to get a random meme from reddit
async def get_meme(meme_subreddits: list[str] = NORMAL_MEME_SUBREDDITS) -> str:
    ACCEPTED_URLS: tuple[str, ...] = (
        "https://v.redd.it/",
        "https://i.redd.it/",
        "https://i.imgur.com/",
    )
    subreddit: str = random.choice(meme_subreddits)
    url = f"https://reddit.com/r/{subreddit}/hot.json"
    if verbose:
        log(f"Getting meme from {url}")
    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
    )
    r.raise_for_status()
    memes = r.json()["data"]["children"]
    random_meme = random.choice(memes)
    if debug:
        log(f"Random meme: {str(random_meme)}")
    random_meme_url: str = str(random_meme["data"]["url"])
    if not random_meme_url.startswith(ACCEPTED_URLS):
        if verbose:
            log("Meme url not accepted, trying again")
        return await get_meme(meme_subreddits=meme_subreddits)
    if random_meme_url in repost_list:
        if verbose:
            log("Meme url in repost list, trying again")
        return await get_meme(meme_subreddits=meme_subreddits)
    update_repost_list(random_meme_url)
    if random_meme_url.startswith("https://v.redd.it/"):
        return get_reddit_video_source(random_meme_url)
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
    await memes_channel.send(await get_meme(meme_subreddits=NORMAL_MEME_SUBREDDITS))


@tasks.loop(hours=2)
async def send_destiny_meme(do_random_check: bool = True):
    # One in four chance of sending a meme
    log("Called send_d2_meme()")
    if do_random_check and random.randint(0, 3):
        return
    log("Passed random check")
    memes_channel = client.get_channel(D2_MEMES_CHANNEL_ID)
    assert isinstance(memes_channel, discord.abc.Messageable)
    await memes_channel.send(await get_meme(meme_subreddits=DESTINY_MEME_SUBREDDITS))


# Compliment @Dabbing Guy#5193 every once and a while
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
        log(
            f"Received message '{message.author}: {message.content}' in '{message.guild}'/'{message.channel}'"
        )

    if message.author == client.user:
        return

    if message.channel.id == CHAT_WITH_SPICE_CHANNEL_ID:
        # If the message is in the chat with spice channel, send a response
        if str(message.content).lower().startswith("hey spice"):
            if verbose:
                log("Saw message in chat with spice channel. Sending response.")
            user_message: str = f"{str(message.author)}: {message.content[10:]}"

            if message.attachments:
                if verbose:
                    log("Message has attachments. Checking if it is text.")
                if message.attachments[0].filename.endswith(".txt"):
                    if verbose:
                        log("Attachment is text. Getting text.")
                    with open("temp.txt", "wb") as f:
                        await message.attachments[0].save(f)
                    with open("temp.txt", "r") as f:
                        user_message += f.read()
                    os.remove("temp.txt")

            async with message.channel.typing():
                res = spice_chat.reply(user_message)
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
        if message.author.id == DABBING_GUY_ID:
            await message.channel.send("You are a good person")
        else:
            await message.channel.send("ur ugly :sick:")
        return
    if message.author.id == DABBING_GUY_ID:
        return
    if message.author.bot:
        return

    # Rate limit to one message every 30 minutes
    if (time.time() - last_sent_time) < 1800:
        return
    if verbose:
        log("Rate limit passed")

    # Insult people talking about val or overwatch
    for test in ["val", "valorant", "overwatch"]:
        if test in message.content.lower().split(" "):
            await message.channel.send(
                "I've been to the Kaaba and back and still can't find your dad"
            )

    # Make it 20% likely to reply
    if random.randint(0, 5):
        return
    if verbose:
        log("Random check passed")

    # Send the response
    log(
        f"Calling send response for '{message.author}: {message.content}' in '{message.guild}'/'{message.channel}'"
    )
    await send_response(message.channel)


client.run(DISCORD_TOKEN)
