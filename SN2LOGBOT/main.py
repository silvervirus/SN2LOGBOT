import discord
from discord.ext import commands
import requests
import os
import re
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_LOG_CHANNEL_ID', 0))

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

EXCLUDED_MODS = ["KismetDebuggerMod", "EventViewerMod", "LineTraceMod", "jsbLuaProfilerMod", "BPModLoaderMod"]

def extract_mod_name(path_string):
    clean = re.sub(r'.*\/mods\/(\d+\/)?', '', path_string)
    return clean.split('/')[0].split('\\')[0]

def parse_log(log_content):
    """Parses UE4SS log content to find mods, errors, and environment info."""
    mods = {}
    lines = log_content.splitlines()
    
    # Extract Environment Info with full version
    version_match = re.search(r"UE4SS - (v[\d\.]+(?:[a-zA-Z0-9\s#]+)?)", log_content)
    ue4ss_version = version_match.group(1) if version_match else "Unknown"
    env_info = f"Subnautica 2 (UE4SS)\nUE4SS: {ue4ss_version}"
    
    # Extract Mods
    for line in lines:
        if "Starting C++ mod" in line:
            m = extract_mod_name(line.split("'")[1])
            mods[m] = "(C++)"
        elif "SDF folder found in mod" in line:
            m = re.search(r"found in mod ([a-zA-Z0-9_\-\.]+)", line)
            if m: mods[m.group(1)] = "(SDF)"
        elif "Mod '" in line and "has enabled" in line:
            m = extract_mod_name(line.split("'")[1])
            if m not in mods: mods[m] = "(Mod)"
        
        lua_match = re.search(r"\[Lua\]\s?\[([^\]]+)\]", line)
        if lua_match:
            m = extract_mod_name(lua_match.group(1))
            if m.upper() not in ["STATUS", "INFO", "LUA", "MOD", "WARNING"] and m not in mods:
                mods[m] = "(Lua/BP)"
                
    filtered_mods = {k: v for k, v in mods.items() if k not in EXCLUDED_MODS}
    
    # Extract Errors and Warnings
    errors = [l for l in lines if any(x in l for x in ["[Error]", "failed", "ArIsError", "ScriptError"])]
    warnings = [l for l in lines if "[Warning]" in l]
    
    return filtered_mods, errors[-15:], warnings[-15:], env_info

async def upload_log_to_gist(content, filename):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    data = {'public': True, 'files': {filename: {'content': content}}}
    response = requests.post('https://api.github.com/gists', json=data, headers=headers)
    if response.status_code == 201:
        return response.json()['files'][filename]['raw_url']
    return None

@bot.command()
async def analyze(ctx):
    if not ctx.message.attachments:
        return await ctx.send(" Please attach a log file!")

    attachment = ctx.message.attachments[0]
    log_content = (await attachment.read()).decode('utf-8', errors='ignore')
    
    mods, errors, warnings, env = parse_log(log_content)

    # Prepare file content
    file_lines = ["=== Detected Mods ==="]
    for name, cat in sorted(mods.items()):
        file_lines.append(f"{name} {cat}")
    
    file_lines.append(f"\n=== Environment & Versions ===\n{env}")
    
    file_lines.append("\n=== Recent Errors ===")
    file_lines.extend(errors if errors else ["No errors found."])
    
    file_lines.append("\n=== Warnings ===")
    file_lines.extend(warnings if warnings else ["No warnings found."])
    
    file_content = "\n".join(file_lines)
    
    output_filename = f"Analysis_{attachment.filename.replace('.log', '.txt')}"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(file_content)

    async with ctx.typing():
        raw_url = await upload_log_to_gist(log_content, attachment.filename)
    
    if raw_url:
        dashboard_url = f"https://silvervirus.github.io/Subnautica-Games-Log-Analyzer/?log={raw_url}"
        await ctx.send(f" **Log Analysis Complete!**\n[View Interactive Dashboard]({dashboard_url})", 
                       file=discord.File(output_filename))
    else:
        await ctx.send(" Failed to upload log to Gist. Check your GitHub Token.")
    
    if os.path.exists(output_filename):
        os.remove(output_filename)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not GITHUB_TOKEN:
        print("Error: Ensure DISCORD_TOKEN and GITHUB_TOKEN are set in .env")
    else:
        bot.run(DISCORD_TOKEN)
