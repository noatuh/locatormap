const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = 3000;

const DATA_FILE = 'drawings.json';
const PHONES_FILE = 'phones.json';

app.use(express.static('public'));
app.use(express.json());

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/save', (req, res) => {
  fs.writeFileSync(DATA_FILE, JSON.stringify(req.body, null, 2));
  res.json({ status: 'saved' });
});

app.get('/load', (req, res) => {
  if (fs.existsSync(DATA_FILE)) {
    const data = fs.readFileSync(DATA_FILE);
    res.json(JSON.parse(data));
  } else {
    res.json([]);
  }
});

app.post('/save_phones', (req, res) => {
  fs.writeFileSync(PHONES_FILE, JSON.stringify(req.body, null, 2));
  res.json({ status: 'phones saved' });
});

app.get('/load_phones', (req, res) => {
  if (fs.existsSync(PHONES_FILE)) {
    const data = fs.readFileSync(PHONES_FILE);
    res.json(JSON.parse(data));
  } else {
    res.json({});
  }
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
