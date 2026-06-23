import discord
from discord.ext import commands
import os
import re
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    print("Error: DISCORD_TOKEN not found in .env file.")
    exit(1)

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

async def send_mod_list(ctx, mods, label):
    """Always sends mod list as a file."""
    if not mods:
        await ctx.send(f"**{label}:** No mods identified.")
        return
        
    with open("mod_list.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(list(set(mods)))))
    
    await ctx.send(f"**{label} ({len(set(mods))} unique mods found):**", file=discord.File("mod_list.txt"))
    os.remove("mod_list.txt")

async def send_errors_as_file(ctx, errors):
    """Writes errors to Errors.txt and sends it."""
    if not errors:
        await ctx.send("No errors found! ✅")
        return
    
    with open("Errors.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(errors))
        
    await ctx.send(f"**Errors found ({len(errors)}):**", file=discord.File("Errors.txt"))
    os.remove("Errors.txt")

async def process_log(ctx, check_mode):
    if not ctx.message.attachments:
        await ctx.send("Please attach a log file!")
        return

    attachment = ctx.message.attachments[0]
    file_path = "temp_log.log"
    await attachment.save(file_path)

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        sn1_update_notice = "\n⚠️ *Note: You are currently running an older version. Please update to BepInEx 5.4.23.5 and Nautilus (v1.0.0-pre.51).*"
        sn2_update_notice = "\n⚠️ *Note: Ensure you are using the latest version of UE4SS (v3.0.1 recommended).*"

        # FIXED: Only flag .cs files found inside modding directories to prevent false positives
        source_code_found = re.search(r"(?:plugins|mods|BepInEx|UE4SS)[^\\/]*[\\/]+.*\.cs", content, re.IGNORECASE)
        
        if "UE4SS" in content:
            version_line = next((line for line in content.splitlines() if "UE4SS - v" in line), "")
            version = version_line.split("UE4SS - ")[1].strip() if version_line else "Unknown"
            install_path = next((line.split("Loading mods from:")[1].strip() for line in content.splitlines() if "Loading mods from:" in line), "Unknown")
            
            if check_mode == "errors":
                errors = [l.strip() for l in content.splitlines() if any(x in l for x in ["[Error]", "[Warning]", "failed"])]
                await send_errors_as_file(ctx, errors)
            else:
                mods = []
                for line in content.splitlines():
                    # Handle C++ mods
                    if "Starting C++ mod" in line:
                        parts = line.split("'")
                        if len(parts) > 1: mods.append(f"{parts[1]} (C++)")
                    
                    # Handle Specific Mod 'Name' enabled pattern
                    elif "Mod '" in line and "has enabled" in line:
                        m = line.split("'")[1]
                        if m == "SDF": mods.append(f"{m} (C++)")
                        elif m == "FileTree": mods.append(f"{m} (Lua/BP)")
                        else: mods.append(f"{m} (Mod)")
                        
                    lua_match = re.search(r"\[Lua\]\s?\[(\w+)\]", line)
                    if lua_match and lua_match.group(1).lower() not in ["lua", "mod"]:
                        mods.append(f"{lua_match.group(1)} (Lua/BP)")
                
                msg = f"**UE4SS Version:** {version}\n**UE4SS Install Path:** `{install_path}`"
                if source_code_found:
                    msg += "\n\n⚠️ **Source Code Detected:** Detected `.cs` files in your mod folder. Ensure you have installed the *compiled* mod (`.dll`)."

                await ctx.send(msg)
                await send_mod_list(ctx, mods, "Detected Mods")

        elif "BepInEx" in content:
            lines = content.splitlines()
            bepinex_ver = next((line.split("BepInEx ")[1].split(" -")[0] for line in lines if "BepInEx" in line), "Unknown")
            is_legacy = "QModManager" in content
            
            if check_mode == "errors":
                errors = [l.strip() for l in lines if any(x in l for x in ["Error", "Exception", "failed"])]
                await send_errors_as_file(ctx, errors)
            else:
                plugins = [line.split("Loading [")[1].split("]")[0] for line in lines if "Loading [" in line]
                msg = f"**BepInEx Version:** {bepinex_ver}"
                if not is_legacy:
                    msg += f" (Update recommended to 5.4.23.5)" + sn1_update_notice
                else:
                    msg += " (Legacy QMod/BepInEx Environment)"
                
                if source_code_found:
                    msg += "\n\n⚠️ **Source Code Detected:** Detected `.cs` files in your mod folder. Ensure you have installed the *compiled* mod (`.dll`)."

                await ctx.send(msg)
                await send_mod_list(ctx, [f"{p} (BepInEx)" for p in plugins], "Plugins found")

    finally:
        if os.path.exists(file_path): os.remove(file_path)

@bot.command()
async def logchk(ctx): await process_log(ctx, "info")

@bot.command()
async def chkers(ctx): await process_log(ctx, "errors")

@bot.command(name="help")
async def help(ctx):
    help_text = "**Available Commands:**\n`!chkers` - Scans log for errors.\n`!logchk` - Displays mod/plugin info.\n`!help` - Shows this list."
    await ctx.send(help_text)

bot.run(TOKEN)
