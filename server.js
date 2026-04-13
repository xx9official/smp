const express = require('express');
const fetch = require('node-fetch');
const https = require('https');

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', 'https://astra-smp.com');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Accept');

  if (req.method === 'OPTIONS') {
    return res.sendStatus(204);
  }

  next();
});

app.get('/', (req, res) => {
  res.json({ ok: true, message: 'Astra API kører' });
});

const insecureHttpsAgent = new https.Agent({
  rejectUnauthorized: false
});

app.post('/apply', async (req, res) => {
  try {
    const data = req.body || {};

    const extra = (data.extra || '') +
      '\n\n🎥 Creator: ' +
      (data.creator_interest || 'Ikke angivet');

    const upstreamPayload = {
      minecraft_username: data.minecraft_username || '',
      discord_user_id: data.discord_user_id || '',
      age: data.age || '',
      playstyle: data.playstyle || '',
      why_join: data.why_join || '',
      experience: data.experience || '',
      extra: extra || ''
    };

    console.log('Sender payload til bot:', upstreamPayload);

    const upstreamResponse = await fetch('https://85.215.229.230:8080/api/apply', {
      method: 'POST',
      agent: insecureHttpsAgent,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(upstreamPayload),
      timeout: 15000
    });

    const raw = await upstreamResponse.text();
    console.log('Svar fra bot:', upstreamResponse.status, raw);

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = { error: raw || 'Bot API svarede ikke med JSON.' };
    }

    return res.status(upstreamResponse.status).json(parsed);
  } catch (err) {
    console.error('Render apply fejl:', err);
    return res.status(500).json({
      error: 'Render kunne ikke sende til bot API.',
      details: err.message || String(err)
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server kører på port ${PORT}`);
});
