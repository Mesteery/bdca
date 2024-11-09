import { ActionRowBuilder, ButtonBuilder, ButtonStyle, ChannelType, InteractionContextType, PermissionFlagsBits, SlashCommandBuilder, SlashCommandChannelOption, SlashCommandIntegerOption, SlashCommandNumberOption, SlashCommandStringOption } from 'discord.js';

const rankChannelOption = (desc) => new SlashCommandChannelOption()
    .setName('rank_channel')
    .setDescription(desc)
    .addChannelTypes(ChannelType.GuildText)
    .setRequired(true);

export const reset = {
    data: new SlashCommandBuilder()
        .setName('reset')
        .addChannelOption(rankChannelOption('Canal des classements où le compteur sera réinitialisé'))
        .setDescription('Réinitialise le compteur des classements dans le canal [rank_channel]')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
        .setContexts(InteractionContextType.Guild),
    async execute(interaction) {
        const channel = interaction.options.getChannel('rank_channel', true, [ChannelType.GuildText]);
        try {
            await channel.setTopic(`${interaction.id}:0`);
        } catch (e) {
            return interaction.reply({
                content: `Impossible de réinitialiser le compteur dans ce canal pour le moment. Réessayez dans ${Math.ceil(e.retryAfter/1000/60)} minutes !`,
                ephemeral: true,
            });
        }
        await interaction.reply({
            content: 'Compteur réinitialisé !',
            ephemeral: true,
        });
    }
}

export const rank = {
    data: new SlashCommandBuilder()
        .setName('rank')
        .addChannelOption(rankChannelOption('Canal où le classement sera affiché'))
        .addStringOption(
            new SlashCommandStringOption()
                .setName('title')
                .setDescription('Titre du classement (ex. DS Maths n°1)')
                .setMaxLength(100)
                .setRequired(true)
        )
        .addNumberOption(
            new SlashCommandNumberOption()
                .setName('scale')
                .setDescription('Barème de notation (20 par défaut)')
                .setMinValue(1)
                .setMaxValue(100)
        )
        .setDescription('Crée un nouveau classement dans le canal [rank_channel]')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
        .setContexts(InteractionContextType.Guild),
    async execute(interaction) {
        const channel = interaction.options.getChannel('rank_channel', true, [ChannelType.GuildText]);
        const title = interaction.options.getString('title', true);
        const scale = interaction.options.getNumber('scale') ?? 20;

        let topic = (channel.topic ?? '').split(':');
        if (topic.length !== 2 || isNaN(topic[0]) || isNaN(topic[1]) || (topic[1] = parseInt(topic[1], 10)) < 0) {
            topic = [interaction.id, 0];
        }
        topic[1]++;

        try {
            await channel.setTopic(topic.join(':'));
        } catch (e) {
            return interaction.reply({
                content: `Impossible de créer un nouveau classement dans ce canal pour le moment. Réessayez dans ${Math.ceil(e.retryAfter/1000/60)} minutes !`,
                ephemeral: true,
            });
        }

        await channel.send({
            content:
`[${topic[1]}] Classement **${title}**
> **Barème** : ${scale}`,
            components: [new ActionRowBuilder().addComponents(
                new ButtonBuilder()
                    .setCustomId(`${topic.join(':')}:${scale}`)
                    .setStyle(ButtonStyle.Primary)
                    .setLabel('Ajouter ma note'),
            )]
        });

        await interaction.reply({ content: 'Classement créé !', ephemeral: true });
    }
}

