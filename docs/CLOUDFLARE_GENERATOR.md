# Cloudflare generator

The generator creates one self-contained ES Module `worker.js`. File embedded
compiled project, scripts, directories, channel adapters, Telegram Bot
API, stateless context, CRM and Firestore REST- integrations.

The user does not need Node.js, Python or Wrangler. He replaces the code.
Starter Worker through Cloudflare Dashboard → Edit Code, creates the listed
at the beginning of the value file via Settings → Variables and Secrets type
presses Deploy.

Secure page `/setup` registers Telegram webhook via `setWebhook` and
Checks it through `getWebhookInfo`. `BOT_TOKEN` is not transmitted to URL browsers.
Incoming Telegram requests are checked by header
`X-Telegram-Bot-Api-Secret-Token`. `SETUP_SECRET` is used only for
Protection of the setting page.

Detailed instructions are localized into the export language and placed in the initial
Comment `worker.js`. The file itself does not contain any secrets.
