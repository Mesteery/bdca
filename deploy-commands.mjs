import assert from 'node:assert';
import { REST, Routes } from 'discord.js';
import * as commands from './commands.mjs';

assert(process.env.CLIENT_TOKEN, 'Missing env CLIENT_TOKEN');
assert(process.env.CLIENT_ID, 'Missing env CLIENT_ID');

const rest = new REST().setToken(process.env.CLIENT_TOKEN);
const body = Object.values(commands).map(c => c.data.toJSON());
console.log(`Started refreshing ${body.length} application (/) commands.`);
await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body });
console.log(`Successfully reloaded ${body.length} application (/) commands.`);
