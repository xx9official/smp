const express = require('express');
const fetch = require('node-fetch');

const app = express();
app.use(express.json());

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const CHANNEL_ID = process.env.APPLICATION_CHANNEL_ID;

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', 'https://astra-smp.com');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

app.post('/apply', async (req, res) => {
  try {
    const data = req.body;

    const embed = {
      title: `Ny ansøgning • ${data.minecraft_username}`,
      color: 0x7AA8FF,
      fields: [
        { name: "Minecraft navn", value: data.minecraft_username, inline: true },
        { name: "Discord ID", value: data.discord_user_id, inline: true },
        { name: "Alder", value: data.age, inline: true },
        { name: "Spillestil", value: data.playstyle },
        { name: "Hvorfor Astra", value: data.why_join },
        { name: "Erfaring", value: data.experience },
        { name: "Ekstra", value: data.extra || "Ingen" }
      ],
      timestamp: new Date().toISOString()
    };

    const response = await fetch(`https://discord.com/api/v10/channels/${CHANNEL_ID}/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bot ${DISCORD_TOKEN}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        embeds: [embed]
      })
    });

    const text = await response.text();

    if (!response.ok) {
      return res.status(500).json({ error: text });
    }

    res.json({ ok: true });

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Kunne ikke sende ansøgning" });
  }
});

app.listen(3000, () => console.log("API kører"));
