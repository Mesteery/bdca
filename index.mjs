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

client.on(Events.InteractionCreate, async (interaction) => {
  try {
    if (interaction.isChatInputCommand()) {
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
        return interaction.reply({ content: `Tu as déjà soumis ta note à ce classement !`, ephemeral: true });

      const gradeInput = new TextInputBuilder()
        .setCustomId('grade')
        .setLabel(`Ta note sur ${scale}`)
        .setMaxLength(1)
        .setMaxLength(scale.length + 5)
        .setPlaceholder('Ex. 18,94')
        .setRequired(true)
        .setStyle(TextInputStyle.Short);

      const modal = new ModalBuilder()
        .setCustomId(`${submitStorageMsg?.id ?? ''}:${resetId}:0x${(bitfield | (1n << BigInt(id-1))).toString(16)}`)
        .setTitle('Ta note')
        .addComponents(new ActionRowBuilder().addComponents(gradeInput));

      await interaction.showModal(modal);
    } else if (interaction.isModalSubmit()) {
      const grade = parseFloat(interaction.fields.getTextInputValue('grade').replace(',', '.'));
      if (isNaN(grade) || grade < 0)
        return interaction.reply({ content: 'Tu dois soumettre une note valide !', ephemeral: true });

      const rankLines = interaction.message.content.split('\n');
      if (rankLines.length < 5) rankLines.push('');
      rankLines[3] = `> **Notes** : ${rankLines.length - 5 + 1}`;

      let i;
      for (i = 5; i < rankLines.length; i++) {
        if (grade > parseFloat(rankLines[i].slice(9))) break;
      }
      rankLines.splice(i, 0, `**${(i - 5 + 1).toString().padStart(2, ' ')}** - ${grade}`);
      for (let j = i + 1; j < rankLines.length; j++) {
        rankLines[j] = `**${(j - 5 + 1).toString().padStart(2, ' ')}${rankLines[j].slice(4)}`;
      }

      await interaction.update({ content: rankLines.join('\n') });
  
      await interaction.followUp({ content: `Ta note a bien été ajouté à ce classement !`, ephemeral: true });

      const dm = await interaction.user.createDM();
      const fstColon = interaction.customId.indexOf(':');
      if (fstColon === 0) {
        await dm.send(interaction.customId.slice(1));
      } else try {
        const message = await dm.messages.fetch(interaction.customId.slice(0, fstColon));
        await message.edit(interaction.customId.slice(fstColon + 1));
      } catch {
        await dm.send(interaction.customId.slice(1))
      };
    }
  } catch (e) {
    console.error(e);
    const fn = interaction.replied || interaction.deferred ? 'followUp' : 'reply';
    interaction[fn]({ content: 'Une erreur est survenue !', ephemeral: true }).catch(() => {});
  }
});
