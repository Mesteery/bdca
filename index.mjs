import assert from 'node:assert';
import { Client, Events, GatewayIntentBits, ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } from 'discord.js';
import * as commands from './commands.mjs';

assert(process.env.CLIENT_TOKEN, 'Missing env CLIENT_TOKEN');

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.DirectMessages],
  rest: {
    rejectOnRateLimit: ['/channels/:id'], // reject when rate limited for topic update (2 requests max per 10m)
  },
});

await client.login(process.env.CLIENT_TOKEN);

console.log('Bot is ready');

function addGradeToRank(rankLines, grade) {
  if (rankLines.length < 3) rankLines.push('');
  let i;
  for (i = 3; i < rankLines.length; i++) {
    if (grade > parseFloat(rankLines[i].slice(9))) break;
  }
  rankLines.splice(i, 0, `**${(i - 3 + 1).toString().padStart(2, ' ')}** - ${grade}`);
  for (let j = i + 1; j < rankLines.length; j++)
    rankLines[j] = `**${(j - 3 + 1).toString().padStart(2, ' ')}${rankLines[j].slice(4)}`;
  return rankLines;
}

client.on(Events.InteractionCreate, async (interaction) => {
  try {
    if (interaction.isChatInputCommand() || interaction.isMessageContextMenuCommand()) {
      const command = commands[interaction.commandName];
      if (!command) return;
      await command.execute(interaction);
    } else if (interaction.isButton()) {
      const [resetId, id, scale] = interaction.customId.split(':');
      if (!interaction.channel.topic?.startsWith(`${resetId}:`))
        return interaction.reply({ content: 'Tu ne peux plus soumettre ta note à ce classement !', ephemeral: true });

      const dm = await interaction.user.createDM();
      const messages = await dm.messages.fetch()
      const submitStorageMsg = messages.findLast(m => m.author.bot && m.content.startsWith(`${resetId}:`));

      const bitfield = submitStorageMsg ? BigInt(submitStorageMsg.content.split(':')[1]) : 0n;
      if (bitfield & (1n << BigInt(id - 1)))
        return interaction.reply({ content: 'Tu as déjà soumis ta note à ce classement !', ephemeral: true });

      const gradeInput = new TextInputBuilder()
        .setCustomId('grade')
        .setLabel(`Ta note sur ${scale}`)
        .setMinLength(1)
        .setMaxLength(scale.length + 4)
        .setPlaceholder('Ex. 18,94')
        .setRequired(true)
        .setStyle(TextInputStyle.Short);

      const modal = new ModalBuilder()
        .setCustomId(`${submitStorageMsg?.id ?? ''}:${resetId}:0x${(bitfield | (1n << BigInt(id-1))).toString(16)}`)
        .setTitle('Ta note')
        .addComponents(new ActionRowBuilder().addComponents(gradeInput));

      await interaction.showModal(modal);
    } else if (interaction.isModalSubmit()) {
      let grade = interaction.fields.getTextInputValue('grade').replace(',', '.');

      // admin tools
      if (interaction.customId.startsWith('remove_grade:')) {
        const message = await interaction.channel.messages.fetch(interaction.customId.slice('remove_grade:'.length)).catch(() => {});
        if (!message) return interaction.reply({ content: 'Le message ciblé n\'existe plus !', ephemeral: true });

        const rankLines = message.content.split('\n');
        if (rankLines.length === 2) return interaction.reply({ content: 'Ce classement ne contient aucune note !', ephemeral: true });

        let i;
        for (i = 3; i < rankLines.length; i++) {
          if (grade === rankLines[i].slice(9)) break;
        }
        rankLines.splice(i, 1);
        for (let j = i; j < rankLines.length; j++)
          rankLines[j] = `**${(j - 3 + 1).toString().padStart(2, ' ')}${rankLines[j].slice(4)}`;

        await message.edit(rankLines.join('\n'));
        return interaction.reply({ content: 'La note a bien été enlevé de ce classement !', ephemeral: true });
      }

      grade = parseFloat(grade);
      if (interaction.customId.startsWith('add_grade:')) {
        const message = await interaction.channel.messages.fetch(interaction.customId.slice('add_grade:'.length)).catch(() => {});
        if (!message) return interaction.reply({ content: 'Le message ciblé n\'existe plus !', ephemeral: true });

        const rankLines = message.content.split('\n');
        await message.edit(addGradeToRank(rankLines, grade).join('\n'));
        return interaction.reply({ content: 'La note a bien été ajoutée à ce classement !', ephemeral: true });
      }

      if (isNaN(grade) || grade < 0) return interaction.reply({ content: 'Tu dois soumettre une note valide !', ephemeral: true });

      const rankLines = interaction.message.content.split('\n');
      await interaction.update(addGradeToRank(rankLines, grade).join('\n'));
      await interaction.followUp({ content: 'Ta note a bien été ajouté à ce classement !', ephemeral: true });

      const dm = await interaction.user.createDM();
      const fstColon = interaction.customId.indexOf(':');
      if (fstColon === 0) {
        await dm.send(interaction.customId.slice(1));
      } else try {
        const message = await dm.messages.fetch(interaction.customId.slice(0, fstColon));
        await message.edit(interaction.customId.slice(fstColon + 1));
      } catch {
        await dm.send(interaction.customId.slice(1));
      };
    }
  } catch (e) {
    console.error(e);
    const fn = interaction.replied || interaction.deferred ? 'followUp' : 'reply';
    interaction[fn]({ content: 'Une erreur est survenue !', ephemeral: true }).catch(() => {});
  }
});
