import discord
from discord.ext import commands, tasks
import aiohttp
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
BACKEND_URL = os.getenv('BACKEND_URL')
GUILD_ID = int(os.getenv('GUILD_ID', 0))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

class BanSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.health_check.start()

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    @tasks.loop(minutes=5)
    async def health_check(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BACKEND_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        print("⚠️ Serveur backend indisponible")
        except Exception as e:
            print(f"❌ Erreur health check: {e}")

    @health_check.before_loop
    async def before_health_check(self):
        await self.bot.wait_until_ready()

    async def api_request(self, method, endpoint, data=None):
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            url = f"{BACKEND_URL}{endpoint}"
            async with self.session.request(method, url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return await resp.json(), resp.status
        except Exception as e:
            return {"error": str(e)}, 500

    @discord.app_commands.command(name="ban", description="Bannir un joueur Roblox")
    @discord.app_commands.describe(
        username="Nom d'utilisateur Roblox",
        reason="Raison du ban",
        duration="Durée en jours (optionnel)"
    )
    async def ban_player(self, interaction: discord.Interaction, username: str, reason: str = "Pas de raison", duration: int = None):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        data = {
            "username": username,
            "reason": reason,
            "banned_by": str(interaction.user),
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id,
            "duration": duration
        }
        
        result, status = await self.api_request("POST", "/api/ban", data)
        
        if status == 200:
            embed = discord.Embed(
                title="✅ Ban réussi",
                description=f"**Joueur:** {username}\n**Raison:** {reason}" + (f"\n**Durée:** {duration} jours" if duration else ""),
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Banni par {interaction.user}")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="unban", description="Débannir un joueur Roblox")
    @discord.app_commands.describe(username="Nom d'utilisateur Roblox")
    async def unban_player(self, interaction: discord.Interaction, username: str):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        result, status = await self.api_request("POST", "/api/unban", {"username": username})
        
        if status == 200:
            embed = discord.Embed(
                title="✅ Débannissement réussi",
                description=f"**Joueur:** {username}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="check", description="Vérifier le statut d'un joueur")
    @discord.app_commands.describe(username="Nom d'utilisateur Roblox")
    async def check_player(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        
        result, status = await self.api_request("GET", f"/api/check-ban/{username}", None)
        
        if status == 200:
            if result.get('is_banned'):
                embed = discord.Embed(
                    title="⚠️ Joueur banni",
                    description=f"**Joueur:** {username}\n**Raison:** {result.get('reason')}\n**Banni par:** {result.get('banned_by')}\n**Date:** {result.get('date')}",
                    color=discord.Color.red()
                )
                if result.get('unban_date'):
                    embed.add_field(name="Débannissement", value=result.get('unban_date'))
            else:
                embed = discord.Embed(
                    title="✅ Joueur non banni",
                    description=f"**Joueur:** {username}",
                    color=discord.Color.green()
                )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="kick", description="Expulser un joueur Roblox du serveur")
    @discord.app_commands.describe(
        username="Nom d'utilisateur Roblox",
        reason="Raison de l'expulsion"
    )
    async def kick_player(self, interaction: discord.Interaction, username: str, reason: str = "Pas de raison"):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        data = {
            "username": username,
            "reason": reason,
            "kicked_by": str(interaction.user),
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id
        }
        
        result, status = await self.api_request("POST", "/api/kick", data)
        
        if status == 200:
            embed = discord.Embed(
                title="✅ Expulsion réussie",
                description=f"**Joueur:** {username}\n**Raison:** {reason}",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="mute", description="Rendre muet un joueur")
    @discord.app_commands.describe(
        username="Nom d'utilisateur Roblox",
        duration="Durée en minutes",
        reason="Raison du mute"
    )
    async def mute_player(self, interaction: discord.Interaction, username: str, duration: int, reason: str = "Pas de raison"):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        data = {
            "username": username,
            "duration": duration,
            "reason": reason,
            "muted_by": str(interaction.user),
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id
        }
        
        result, status = await self.api_request("POST", "/api/mute", data)
        
        if status == 200:
            embed = discord.Embed(
                title="🔇 Mute appliqué",
                description=f"**Joueur:** {username}\n**Durée:** {duration} minutes\n**Raison:** {reason}",
                color=discord.Color.yellow(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="warn", description="Avertir un joueur")
    @discord.app_commands.describe(
        username="Nom d'utilisateur Roblox",
        reason="Raison de l'avertissement"
    )
    async def warn_player(self, interaction: discord.Interaction, username: str, reason: str = "Pas de raison"):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        data = {
            "username": username,
            "reason": reason,
            "warned_by": str(interaction.user),
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id
        }
        
        result, status = await self.api_request("POST", "/api/warn", data)
        
        if status == 200:
            warns = result.get('total_warns', 1)
            embed = discord.Embed(
                title="⚠️ Avertissement ajouté",
                description=f"**Joueur:** {username}\n**Raison:** {reason}\n**Total avertissements:** {warns}",
                color=discord.Color.yellow(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="warns", description="Voir les avertissements d'un joueur")
    @discord.app_commands.describe(username="Nom d'utilisateur Roblox")
    async def check_warns(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        
        result, status = await self.api_request("GET", f"/api/warns/{username}", None)
        
        if status == 200:
            warns = result.get('warns', [])
            if warns:
                description = f"**Total:** {len(warns)} avertissements\n\n"
                for i, warn in enumerate(warns[:10], 1):
                    description += f"{i}. {warn['reason']} (par {warn['warned_by']})\n"
                embed = discord.Embed(
                    title=f"⚠️ Avertissements de {username}",
                    description=description,
                    color=discord.Color.yellow()
                )
            else:
                embed = discord.Embed(
                    title=f"✅ {username}",
                    description="Aucun avertissement",
                    color=discord.Color.green()
                )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="history", description="Voir l'historique d'un joueur")
    @discord.app_commands.describe(username="Nom d'utilisateur Roblox")
    async def player_history(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        
        result, status = await self.api_request("GET", f"/api/history/{username}", None)
        
        if status == 200:
            history = result.get('history', [])
            if history:
                description = ""
                for action in history[:15]:
                    description += f"**{action['type'].upper()}** - {action['reason']}\n{action['date']}\n\n"
                embed = discord.Embed(
                    title=f"📋 Historique de {username}",
                    description=description[:2000],
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title=f"📋 {username}",
                    description="Aucun historique",
                    color=discord.Color.blue()
                )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ {result.get('error', 'Erreur inconnue')}", ephemeral=True)

    @discord.app_commands.command(name="bans", description="Voir tous les bans actifs")
    async def list_bans(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        result, status = await self.api_request("GET", "/api/bans", None)
        
        if status == 200:
            bans = result.get('bans', [])
            if bans:
                description = f"**Total:** {len(bans)} bans actifs\n\n"
                for ban in bans[:10]:
                    description += f"👤 {ban['roblox_username']}\n📝 {ban['reason']}\n"
                embed = discord.Embed(
                    title="🔒 Bans actifs",
                    description=description[:2000],
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="🔒 Aucun ban actif",
                    description="La communauté est calme!",
                    color=discord.Color.green()
                )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Erreur", ephemeral=True)

    @discord.app_commands.command(name="stats", description="Voir les statistiques")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        result, status = await self.api_request("GET", "/api/stats", None)
        
        if status == 200:
            embed = discord.Embed(
                title="📊 Statistiques",
                description=f"**Bans:** {result.get('total_bans', 0)}\n**Kicks:** {result.get('total_kicks', 0)}\n**Mutes:** {result.get('total_mutes', 0)}\n**Avertissements:** {result.get('total_warns', 0)}",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Erreur", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} est connecté")
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"❌ Erreur sync: {e}")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Permission refusée", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Erreur: {str(error)}", ephemeral=True)

async def main():
    async with bot:
        await bot.add_cog(BanSystem(bot))
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
