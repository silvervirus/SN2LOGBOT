# SN2LOGBOT
a bot to check Subnautica2 , Stable Belowzero and Subnautica , legacy Subnautica !logchk and !chkerrs !help
To get your Discord Log Checker bot running from scratch, follow this setup guide. This covers everything from creating the bot in Discord to installing the necessary Python tools.
Discord Game Log Checker

Features

!LogCheck: Analyzes a log file to extract mod information and version data.

!CheckErrors: Scans logs for common error patterns and exceptions.

Automated Detection: Supports Subnautica 2 (UE4SS) and Subnautica/BelowZero (BepInEx).

Setup Guide

Requirements

```Python 3.8+```

You will find the requirements.txt file included in the source code.

Configuration & Getting Your Token

Create a .env file in the root directory.

How to get your Discord Bot Token:

Go to the Discord Developer Portal (https://discord.com/developers/applications).

Click on your Application.

On the left sidebar, click Bot.

Scroll down to the Token section and click Reset Token.

Copy the token provided. Keep this secret!

Add your token to the .env file:

```DISCORD_TOKEN=your_token_here```

Security Warning: Never share your token or upload the .env file to GitHub. If your token is exposed, reset it immediately in the Developer Portal.

Installation & Running

Before running the commands, open your terminal and cd into the folder containing your main.py, requirements.txt, and .env files.

Install dependencies

```pip install -r requirements.txt```

Run the bot

```python main.py```
