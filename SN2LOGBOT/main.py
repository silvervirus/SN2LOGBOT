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

# List of mods to exclude from the final report
EXCLUDED_MODS = [
    "KismetDebuggerMod", 
    "EventViewerMod", 
    "LineTraceMod", 
    "jsbLuaProfilerMod", 
    "BPModLoaderMod",
    "ConsoleEnabler",
    "CheatManagerEnabler",
    "Adjustable Lights",
    "Inspect Tools"
]

def extract_mod_name(path_string):
    """Cleans paths to find the mod name, stripping numeric IDs and folder prefixes."""
    clean = re.sub(r'.*\/mods\/(\d+\/)?', '', path_string)
    return clean.split('/')[0].split('\\')[0]

async def send_mod_list(ctx, mods_dict, label, validations=None):
    """Sends a text file containing the list of detected mods and validation warnings."""
    # Filter out excluded mods before reporting
    filtered_mods = {k: v for k, v in mods_dict.items() if k not in EXCLUDED_MODS}
    
    if not filtered_mods and not validations:
        await ctx.send(f"**{label}:** No non-default mods identified.")
        return
    
    lines = [f"{name} {cat}" for name, cat in sorted(filtered_mods.items())]
    if validations:
        lines.append("\n--- Mod Validation Warnings ---")
        lines.extend(validations)
    
    with open("mod_list.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    await ctx.send(f"**{label} ({len(filtered_mods)} unique mods found):**", file=discord.File("mod_list.txt"))
    os.remove("mod_list.txt")

async def send_errors_as_file(ctx, errors):
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

        sn2_update_notice = "\n⚠️ *Note: Ensure you are using the latest version of UE4SS (v3.0.1+).*"
        source_code_found = re.search(r"[\w\.\-\/]+\.cs", content, re.IGNORECASE)

        if "UE4SS" in content:
            version_line = next((line for line in content.splitlines() if "UE4SS - v" in line), "")
            version = version_line.split("UE4SS - ")[1].split(" ")[0].strip() if version_line else "Unknown"
            install_path = next((line.split("Loading mods from:")[1].strip() for line in content.splitlines() if "Loading mods from:" in line), "Unknown")
            
            if check_mode == "errors":
                errors = [l.strip() for l in content.splitlines() if any(x in l for x in ["[Error]", "[Warning]", "failed"])]
                await send_errors_as_file(ctx, errors)
            else:
                mods_dict = {}
                validations = []
                for line in content.splitlines():
                    if "[Lua] [WARNING]" in line and "folder detected" in line:
                        validations.append(line.split("[Lua] [WARNING]")[1].strip())
                    
                    if "Starting C++ mod" in line:
                        m = extract_mod_name(line.split("'")[1])
                        mods_dict[m] = "(C++)"
                    elif "SDF folder found in mod" in line:
                        m = re.search(r"found in mod ([a-zA-Z0-9_\-\.]+)", line)
                        if m: mods_dict[m.group(1)] = "(SDF)"
                    elif "Mod '" in line and "has enabled" in line:
                        m = extract_mod_name(line.split("'")[1])
                        if m not in mods_dict: mods_dict[m] = "(Lua or C++)"
                    
                    lua_match = re.search(r"\[Lua\]\s?\[([^\]]+)\]", line)
                    if lua_match:
                        m = extract_mod_name(lua_match.group(1))
                        if m.upper() not in ["STATUS", "INFO", "LUA", "MOD", "WARNING"] and m not in mods_dict:
                            mods_dict[m] = "(Lua)"
                
                msg = f"**Environment:** Subnautica 2 (UE4SS {version})\n**Path:** `{install_path}`"
                if "3.0.1" not in version: msg += sn2_update_notice
                if source_code_found: msg += "\n\n⚠️ **Source Code Detected:** Detected `.cs` files. Ensure you have installed the *compiled* mod (`.dll`)."
                await ctx.send(msg)
                await send_mod_list(ctx, mods_dict, "Detected Mods", validations)

        elif "BepInEx" in content:
            plugins = {}
            bepinex_version_str = None
            nautilus_version_str = None

            # Helper function to convert version strings into numeric lists for safe comparison
            def parse_version(v_str):
                if not v_str: return []
                return [int(x) for x in v_str.replace(",", ".").split(".") if x.strip().isdigit()]

            # Parse lines for mods and framework versions safely
            for line in content.splitlines():
                if "Loading [" in line and "]" in line:
                    try:
                        raw_name = line.split("Loading [")[1].split("]")[0]
                        mod_name = extract_mod_name(raw_name)
                        plugins[mod_name] = "(BepInEx)"
                    except IndexError:
                        continue

                # Detect BepInEx Version Line
                if "BepInEx" in line and "stable" in line.lower() and not bepinex_version_str:
                    for word in line.split():
                        if any(c.isdigit() for c in word) and "." in word:
                            bepinex_version_str = word.strip("()[]")
                            break

                # Detect Nautilus Version Line
                if "Loading [Nautilus" in line:
                    try:
                        nautilus_version_str = line.split("Nautilus")[1].split("]")[0].strip()
                    except IndexError:
                        pass

            # Target baseline checks
            target_bepinex = [5, 4, 23, 5]
            target_nautilus = [1, 0, 0, 51]

            b_ver = parse_version(bepinex_version_str)
            n_ver = parse_version(nautilus_version_str)

            # Build custom warnings if versions are low
            notices = []
            if b_ver and b_ver < target_bepinex:
                notices.append(f"⚠️ BepInEx is outdated ({bepinex_version_str or 'Unknown'}). Update to 5.4.23.5 or newer.")
            if n_ver and n_ver < target_nautilus:
                notices.append(f"⚠️ Nautilus is outdated ({nautilus_version_str or 'Unknown'}). Update to 1.0.0.51 or newer.")

            sn1_update_notice = "\n" + "\n".join(notices) if notices else ""

            await ctx.send(f"**Environment:** Subnautica 1 / Below Zero (BepInEx){sn1_update_notice}")
            await send_mod_list(ctx, plugins, "Plugins found")
            
        else:
            await ctx.send("Unknown log format.")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

@bot.command()
async def logchk(ctx): await process_log(ctx, "info")

@bot.command()
async def chkers(ctx): await process_log(ctx, "errors")

@bot.command(name="help")
async def help(ctx):
    await ctx.send("**Available Commands:**\n`!chkers` - Scans log for errors.\n`!logchk` - Analyzes log and displays mod info.")

bot.run(TOKEN)

