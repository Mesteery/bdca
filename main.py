import os
import re
from typing import Optional
import discord
from discord import app_commands, Interaction
from discord.ui import Modal, TextInput, View, Button
from utils import add_grade_to_rank, build_rank_message, fill_rank, filter_real_grades, parse_data_lines, parse_message_rank, build_data_lines

TOKEN = os.getenv("CLIENT_TOKEN")
if not TOKEN:
    raise ValueError("Missing env CLIENT_TOKEN")

class Client(discord.Client):
  def __init__(self, *, intents: discord.Intents):
    super().__init__(intents=intents, max_ratelimit_timeout=30)
    self.tree = app_commands.CommandTree(self)

  async def setup_hook(self):
    await self.tree.sync()
    self.add_dynamic_items(AddGradeButton)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.dm_messages = True

client = Client(intents=intents)

@client.event
async def on_ready():
  print(f'Logged in as {client.user} (ID: {client.user.id})')

class AddGradeModal(Modal, title="Ta note"):
  def __init__(self, submit_storage_msg_id: id, reset_id: int, bf: int, scale: int):
    super().__init__()

    self.submit_storage_msg_id: int = submit_storage_msg_id
    self.reset_id: str = reset_id
    self.bf: int = bf

    self.grade = TextInput(
      label="Ta note",
      style=discord.TextStyle.short,
      min_length=1,
      max_length=len(str(scale)) + 4,
      placeholder="Ex. 18,94",
      required=True
    )

    self.add_item(self.grade)

  async def on_submit(self, interaction: Interaction):
    grade = self.grade.value.replace(',', '.')
    try:
      grade = float(grade)
    except ValueError:
      grade = None
    if grade is None or grade < 0:
      return await interaction.response.send_message("Tu dois soumettre une note valide !", ephemeral=True)
    
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    title, data_lines, rank_lines = parse_message_rank(interaction.message.content)

    rank_lines = add_grade_to_rank(filter_real_grades(rank_lines), grade)

    rank_lines = fill_rank(parse_data_lines(data_lines), rank_lines)

    await interaction.message.edit(content=build_rank_message(title, data_lines, rank_lines))
    await interaction.followup.send("Ta note a bien été ajoutée à ce classement !", ephemeral=True)
  
    dm = await interaction.user.create_dm()
    if self.submit_storage_msg_id == -1:
      await dm.send(f"{self.reset_id}:0x{self.bf:x}")
    else:
      try:
        message = await dm.fetch_message(self.submit_storage_msg_id)
        await message.edit(content=f"{self.reset_id}:0x{self.bf:x}")
      except:
        await dm.send(f"{self.reset_id}:0x{self.bf:x}")

class AddGradeButton(discord.ui.DynamicItem[Button], template=r'(?P<reset_id>[0-9]+):(?P<idx>[0-9]+):(?P<scale>[0-9]+)'):
  def __init__(self, reset_id: int, idx: int, scale: int):
    super().__init__(
      Button(
        label='Ajouter ma note',
        style=discord.ButtonStyle.primary,
        custom_id=f'{reset_id}:{idx}:{scale}',
      )
    )
    self.reset_id: int = reset_id
    self.idx: int = idx
    self.scale: int = scale

  @classmethod
  async def from_custom_id(cls, interaction: Interaction, item: Button, match: re.Match[str], /):
    return cls(int(match['reset_id']), int(match['idx']), int(match['scale']))

  async def callback(self, interaction: Interaction) -> None:
    if not interaction.channel or not interaction.channel.topic or not interaction.channel.topic.startswith(f"{self.reset_id}:"):
      return await interaction.response.send_message("Tu ne peux plus soumettre ta note à ce classement !", ephemeral=True)

    dm = await interaction.user.create_dm()
    submit_storage_msg: Optional[discord.Message] = None
    async for message in dm.history():
      if message.author == client.user and message.content.startswith(f"{self.reset_id}:"):
        submit_storage_msg = message
        break
    
    bitfield = int(submit_storage_msg.content.split(":")[1], 16) if submit_storage_msg else 0

    if bitfield & (1 << (self.idx - 1)):
      return await interaction.response.send_message("Tu as déjà soumis ta note à ce classement !", ephemeral=True)
    
    modal = AddGradeModal(-1 if submit_storage_msg is None else submit_storage_msg.id, self.reset_id, self.idx, self.scale)
    await interaction.response.send_modal(modal)

@client.tree.command()
@app_commands.describe(
  channel="Canal où le classement sera affiché",
  title="Titre du classement",
  scale="Barème de notation (20 par défaut)"
)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.checks.has_permissions(manage_guild=True)
async def rank(interaction: Interaction, channel: discord.TextChannel, title: app_commands.Range[str, 1, 100], scale: Optional[app_commands.Range[int, 1, 100]] = 20):
    """Crée un nouveau classement dans le canal [channel]"""
    
    topic = (channel.topic or "").split(":")
    if len(topic) != 2 or not topic[0].isnumeric() or not topic[1].isnumeric() or int(topic[1]) < 0:
      topic = [str(interaction.id), 1]
    else:
      topic[1] = int(topic[1]) + 1

    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
      await channel.edit(topic=f"{topic[0]}:{topic[1]}")
    except discord.RateLimited as e:
      return await interaction.followup.send(f"Impossible de créer un nouveau classement dans ce canal pour le moment. Réessayez dans {e.retry_after/60:.1f} minutes !", ephemeral=True)
    
    view = View(timeout=None)
    view.add_item(AddGradeButton(int(topic[0]), topic[1], scale))
    await channel.send(build_rank_message(f"[{topic[1]}] Classement **{title}**", build_data_lines({'scale':scale}), []), view=view)
    await interaction.followup.send("Classement crée !", ephemeral=True)

@client.tree.command()
@app_commands.describe(
  channel="Canal des classements où le compteur sera réinitialisé",
)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.checks.has_permissions(manage_guild=True)
async def reset(interaction: Interaction, channel: discord.TextChannel):
    """Réinitialise le compteur des classements dans le canal [channel]"""

    try:
      await channel.edit(topic=f"{interaction.id}:0")
    except discord.RateLimited as e:
      return await interaction.response.send_message(f"Impossible de créer un nouveau classement dans ce canal pour le moment. Réessayez dans {e.retry_after/1000/60:.1f} minutes !", ephemeral=True)
    
    await interaction.response.send_message("Compteur réinitialisé !", ephemeral=True)

class AdminAddGradeModal(Modal, title="Ajouter une note (outil admin)"):
  def __init__(self, target_message_id: int):
    super().__init__()
    self.target_message_id: int = target_message_id

  grade = TextInput(
    label="Note",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 18,94",
    required=True
  )

  async def on_submit(self, interaction: Interaction):
    grade = self.grade.value.replace(',', '.')
    try:
      grade = float(grade)
    except ValueError:
      grade = None
    if grade is None or grade < 0:
      return await interaction.response.send_message("Tu dois soumettre une note valide !", ephemeral=True)
    
    message = interaction.channel and await interaction.channel.fetch_message(self.target_message_id)
    if not message:
      return await interaction.response.send_message("Le message ciblé n'existe plus !", ephemeral=True)
    
    await interaction.response.defer(thinking=True, ephemeral=True)

    title, data_lines, rank_lines = parse_message_rank(message.content)
    rank_lines = add_grade_to_rank(filter_real_grades(rank_lines), grade)
    rank_lines = fill_rank(parse_data_lines(data_lines), rank_lines)

    await message.edit(content=build_rank_message(title, data_lines, rank_lines))

    await interaction.followup.send("La note a bien été ajoutée à ce classement !", ephemeral=True)

@client.tree.context_menu(name="Ajouter une note (admin)")
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.checks.has_permissions(manage_guild=True)
async def add_grade(interaction: Interaction, message: discord.Message):
  """Ajoute une note à ce classement"""

  if message.author != client.user or message.is_system():
    return await interaction.response.send_message("Le message ciblé n'est pas un classement !", ephemeral=True)
  
  await interaction.response.send_modal(AdminAddGradeModal(message.id))

class AdminRemoveGradeModal(Modal, title="Enlever une note (outil admin)"):
  def __init__(self, target_message_id: int):
    super().__init__()
    self.target_message_id: int = target_message_id

  grade = TextInput(
    label="Note",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 18,94",
    required=True
  )

  async def on_submit(self, interaction: Interaction):
    grade = self.grade.value.replace(',', '.')
    try:
      grade = float(grade)
    except ValueError:
      grade = None
    if grade is None or grade < 0:
      return await interaction.response.send_message("Tu dois soumettre une note valide !", ephemeral=True)

    message = interaction.channel and await interaction.channel.fetch_message(self.target_message_id)
    if not message:
      return await interaction.response.send_message("Le message ciblé n'existe plus !", ephemeral=True)
    
    title, data_lines, rank_lines = parse_message_rank(message.content)

    rank_lines = filter_real_grades(rank_lines)

    i = 0
    for i, line in enumerate(rank_lines):
      if float(line[9:]) == grade:
        break
    else:
      return await interaction.response.send_message("Cette note n'existe pas dans ce classement !", ephemeral=True)
    
    await interaction.response.defer(thinking=True, ephemeral=True)

    rank_lines.pop(i)
    for j in range(i, len(rank_lines)):
      rank_lines[j] = f"**{(j + 1):>2}{rank_lines[j][4:]}"

    rank_lines = fill_rank(parse_data_lines(data_lines), rank_lines)

    await message.edit(content=build_rank_message(title, data_lines, rank_lines))
    await interaction.followup.send("La note a bien été enlevé de ce classement !", ephemeral=True)

@client.tree.context_menu(name="Enlever une note (admin)")
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.checks.has_permissions(manage_guild=True)
async def remove_grade(interaction: Interaction, message: discord.Message):
  """Enleve une note à ce classement"""

  if message.author != client.user or message.is_system():
    return await interaction.response.send_message("Le message ciblé n'est pas un classement !", ephemeral=True)
  
  if len(message.content.splitlines()) < 3:
    return await interaction.response.send_message('Ce classement ne contient aucune note !', ephemeral=True)
  
  await interaction.response.send_modal(AdminRemoveGradeModal(message.id))

class AdminFillGradesModal(Modal, title="Estimer les notes manquantes (outil admin)"):
  def __init__(self, target_message_id: int):
    super().__init__()
    self.target_message_id: int = target_message_id

  
  total_grades = TextInput(
    label="Nombre total de notes",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 47",
    required=True
  )

  minmax_grade = TextInput(
    label="Note minimale et maximale",
    style=discord.TextStyle.short,
    min_length=3,
    placeholder="Ex. 3,4|18,94",
    required=True
  )

  median = TextInput(
    label="Médiane",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 11,4",
    required=True
  )

  mean = TextInput(
    label="Moyenne",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 11,2",
    required=True
  )

  std = TextInput(
    label="Écart-type",
    style=discord.TextStyle.short,
    min_length=1,
    placeholder="Ex. 3,7",
    required=False,
    default="0"
  )

  async def on_submit(self, interaction: Interaction):
    minmax_grade = self.minmax_grade.value.split('|')
    median = self.median.value.replace(',', '.')
    mean = self.mean.value.replace(',', '.')
    std = self.std.value.replace(',', '.')
    total_grades = self.total_grades.value

    try:
      min_grade = float(minmax_grade[0].replace(',', '.'))
      max_grade = float(minmax_grade[1].replace(',', '.'))
      median = float(median)
      mean = float(mean)
      std = float(std)
      total_grades = int(total_grades)
    except ValueError:
      return await interaction.response.send_message("Tu dois soumettre des valeurs valides !", ephemeral=True)

    message = interaction.channel and await interaction.channel.fetch_message(self.target_message_id)
    if not message:
      return await interaction.response.send_message("Le message ciblé n'existe plus !", ephemeral=True)
    
    await interaction.response.defer(thinking=True, ephemeral=True)

    title, old_data, rank_lines = parse_message_rank(message.content)

    data = {
      'total': total_grades,
      'min': min_grade,
      'max': max_grade,
      'median': median,
      'mean': mean,
      'std': std,
      'scale': parse_data_lines(old_data)['scale'],
    }

    rank_lines = fill_rank(data, filter_real_grades(rank_lines))

    await message.edit(content=build_rank_message(title, build_data_lines(data), rank_lines))
    await interaction.followup.send("Le classement a bien été complété !", ephemeral=True)

@client.tree.context_menu(name="Notes manquantes (admin)")
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.checks.has_permissions(manage_guild=True)
async def fill_grades(interaction: Interaction, message: discord.Message):
  """Complète les notes manquantes de ce classement en estimant les valeurs"""

  if message.author != client.user or message.is_system():
    return await interaction.response.send_message("Le message ciblé n'est pas un classement !", ephemeral=True)
  
  if len(message.content.splitlines()) < 3:
    return await interaction.response.send_message('Ce classement ne contient aucune note !', ephemeral=True)
  
  await interaction.response.send_modal(AdminFillGradesModal(message.id))


client.run(TOKEN)

