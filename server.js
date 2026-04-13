const express = require('express');
const fetch = require('node-fetch');

const app = express();
app.use(express.json());

// Test route (valgfri men god til at tjekke)
app.get('/', (req, res) => {
  res.send('Astra API kører');
});

app.post('/apply', async (req, res) => {
  try {
    const data = req.body;

    // Saml creator + extra
    const extra = (data.extra || "") +
      "\n\n🎥 Creator: " +
      (data.creator_interest || "Ikke angivet");

    const response = await fetch('http://85.215.229.230:8080/api/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        minecraft_username: data.minecraft_username,
        discord_user_id: data.discord_user_id,
        age: data.age,
        playstyle: data.playstyle,
        why_join: data.why_join,
        experience: data.experience,
        extra: extra
      })
    });

    const text = await response.text();

    res.status(response.status).send(text);

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Kunne ikke sende ansøgning" });
  }
});

// Render kræver PORT env
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log("Server kører på port", PORT);
});
