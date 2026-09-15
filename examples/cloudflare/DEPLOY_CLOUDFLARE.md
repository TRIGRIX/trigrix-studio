# Web Studio - Application for the Project in Cloudflare



This archive contains one common Worker for selected channels: each incoming request is routed by its own webhook path. Separate copies of the channel code are not required.

## 1. Selected channels


### Telegram (`telegram`)

- webhook path: `/webhook/telegram`
- Account ID: `default`
- secret ENV: `WEBHOOK_SECRET`

Create a bot through `@BotFather`, save the token to ENV `BOT_TOKEN` and install the webhook helper script after deployment.




## 2. Yes bot (Telegram)

1. Open Telegram and find `@BotFather`.
2. Create a bot command `/newbot` and save the token.
3. Set the name **Your bot name**.
4. About: **Company assistant**.
5. Description: **Selection of web services and collection of brief**.
6. In `/setcommands` state:

   `start - Main menu`



## 3. Service team

If the project sends requests, create a group, add a bot, issue the right to send messages and receive it Chat ID through helper `tools/check_bot.py` or a temporary diagnostic bot.

## 4. Cloudflare Worker

1. Install Node.js and Wrangler: `npm install -g wrangler`.
2. Open Cloudflare Dashboard → Workers & Pages and sign in.
3. Unpack the archive and open the terminal in this folder.
4. Authorize: `wrangler login`.
5. Add the secrets:

   `wrangler secret put BOT_TOKEN`

   `wrangler secret put WEBHOOK_SECRET`

6. Add the usual Variables in the Worker settings:

   `ADMIN_CHAT_ID` — Chat ID for new applications

7. Run `wrangler deploy` and copy URL Worker.

The project does not require KV, D1, R2 or Durable Objects to execute the script. Firestore, if enabled, is called through official REST API.

## 5. Webhook and


1. Set locally token ENV Telegram, `WEBHOOK_SECRET` and `WORKER_URL`.
2. Do `python tools/set_webhook.py`.
3. Do `python tools/check_webhook.py`.

For Meta/Viber, register each path from Section 1 on one URL Worker. Make sure the request signatures and verification token match ENV.

## 6. Validation

Go through one script in each selected channel and check Worker Logs. Buttons, lists, and attachments are validated by a validator before export; unsupported features receive a fallback or warning.

## 7. Cloudflare Free Email


Cloudflare Free Email is turned off. Configure it visually in TRIGRIX Studio; for arbitrary recipients, use Email API.


## 8. CRM and Firebase

- CRM tokens and Firebase credentials are specified only by commands `wrangler secret put ...` from the list above.
- Check Base URL, pipeline/status and mapping before publication.
- Firestore records only structured leads on stable `lead_id`; messages are not saved.
- For `/export_leads*`, there must be an “Export leads” block with an administrative Telegram recipient.
