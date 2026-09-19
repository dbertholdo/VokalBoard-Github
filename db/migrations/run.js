const fs = require('fs');
const { Client } = require('pg');

async function run() {
  const client = new Client({
    connectionString: 'postgresql://postgres:oNcRxXboMcLRXHGdystfcbWygGqNYSx@iriguchi.proxy.rlwy.net:15548/railway'
  });
  
  try {
    await client.connect();
    console.log('Conectado ao banco de dados com sucesso!');
    const sql = fs.readFileSync('CONSOLIDATED_2026-09-19_pending_since_0915.sql', 'utf8');
    await client.query(sql);
    console.log('Migração executada com sucesso!');
  } catch (err) {
    console.error('Erro na migração:', err);
  } finally {
    await client.end();
  }
}

run();