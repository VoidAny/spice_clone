# Spice Clone

This bot is meant to be a clone of my friend (named Spice) on our discord server. This is nothing more than a joke.

## Usage

to use this, make a `.env` file in the working directory of `spice_clone.py` and populate it with:

- `DISCORD_TOKEN` - the token for the bot
- `OPENAI_API_KEY` - an api key for openai. Only necessary if you plan to use the spicegpt feature.

then run `python spice_clone.py` and the bot should be online. I would recommend running this on a server for constant uptime.

## Features

- Sends memes occasionally and when prompted with "spice, send a meme"
- Downloads videos from reddit if the selected meme is a video and saves it in a folder named media. This folder can then be hosted using nginx to allow people to access the videos.
- Can talk using chatgpt in a given channel
- Can be set to occasionally compliment its creator
- Source code is poorly written and would be very difficult for anyone to actually use in their own server
