import { ActionRowBuilder, ApplicationCommandType, ButtonBuilder, ButtonStyle, ChannelType, ContextMenuCommandBuilder, InteractionContextType, Locale, ModalBuilder, PermissionFlagsBits, SlashCommandBuilder, SlashCommandChannelOption, SlashCommandNumberOption, SlashCommandStringOption, TextInputBuilder, TextInputStyle } from 'discord.js';

const rankChannelOption = (desc) => new SlashCommandChannelOption()
    .setName('rank_channel')
    .setDescription(desc)
    .addChannelTypes(ChannelType.GuildText)
    .setRequired(true);

export const addGrade = {
    data: new ContextMenuCommandBuilder()
        .setName('addGrade')
        .setNameLocalization(Locale.French, 'Ajouter une note (admin)')
        .setType(ApplicationCommandType.Message)
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
        .setContexts(InteractionContextType.Guild),
    async execute(interaction) {
        if (interaction.targetMessage.author.id !== interaction.client.user.id || interaction.targetMessage.author.system)
          return interaction.reply({ content: "Le message ciblé n'est pas un classement !", ephemeral: true });

        const gradeInput = new TextInputBuilder()
            .setCustomId('grade')
            .setLabel(`Note`)
            .setMinLength(1)
            .setPlaceholder('Ex. 18,94')
            .setRequired(true)
            .setStyle(TextInputStyle.Short);

      const modal = new ModalBuilder()
        .setCustomId(`add_grade:${interaction.targetId}`)
        .setTitle('Ajouter une note (outil admin)')
        .addComponents(new ActionRowBuilder().addComponents(gradeInput));

        await interaction.showModal(modal);
    }
}

export const removeGrade = {
    data: new ContextMenuCommandBuilder()
        .setName('removeGrade')
        .setNameLocalization(Locale.French, 'Enlever une note (admin)')
        .setType(ApplicationCommandType.Message)
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
        .setContexts(InteractionContextType.Guild),
    async execute(interaction) {
        if (interaction.targetMessage.author.id !== interaction.client.user.id || interaction.targetMessage.author.system)
            return interaction.reply({ content: "Le message ciblé n'est pas un classement !", ephemeral: true });

        if (interaction.targetMessage.content.split('\n').length === 2)
            return interaction.reply({ content: 'Ce classement ne contient aucune note !', ephemeral: true });

        const gradeInput = new TextInputBuilder()
            .setCustomId('grade')
            .setLabel(`Note à enlever`)
            .setMinLength(1)
            .setPlaceholder('Ex. 18,94')
            .setRequired(true)
            .setStyle(TextInputStyle.Short);

        const modal = new ModalBuilder()
            .setCustomId(`remove_grade:${interaction.targetId}`)
            .setTitle('Enlever une note (outil admin)')
            .addComponents(new ActionRowBuilder().addComponents(gradeInput));

        await interaction.showModal(modal);
    }
}

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
                content: `Impossible de réinitialiser le compteur dans ce canal pour le moment. Réessayez dans ${Math.ceil(e.retryAfter/1000/60) + 1} minutes !`,
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
                content: `Impossible de créer un nouveau classement dans ce canal pour le moment. Réessayez dans ${Math.ceil(e.retryAfter/1000/60) + 1} minutes !`,
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

