# Web Studio - Application for the Project in Docker



The Docker archive contains one common runtime for selected channels. Telegram uses polling, other channels are accepted by one webhook server and differ in path.

## Selected channels


- **Telegram (`telegram`)** — `/webhook/telegram`, Account ID `default`, secret ENV `WEBHOOK_SECRET`.



## Telegram

1. Open Telegram and find `@BotFather`.
2. Create a bot command `/newbot` and save the token.
3. Set up the name, About and Description.
4. In `/setcommands` state:

   `start - Main menu`



## Variables surroundings

Copy `.env.example` into `.env` and complete:

- `BOT_TOKEN` - Telegram bot token; secret, don't publish it.

- `ADMIN_CHAT_ID` — Chat ID for new applications.


## Docker CLI

1. Install Docker Desktop or Docker Engine.
2. Open the terminal in the project folder.
3. Do `docker compose up -d --build`.
4. Check `docker compose ps`.
5. Look at the logs: `docker compose logs -f`.

6. Open the bot in Telegram and send `/start`.


Ports are not required if only Telegram is selected. If any non-Telegram channel is enabled, publish `8080:8080`, configure public HTTPS reverse proxy and direct all paths from the list above to it.

## Portainer

1. Open Portainer and select Environment.
2. Open **Stacks** → **Add stack**.
3. Set the stack name and select the compose file download.
4. Add the contents `compose.yaml`.
5. Add the environment variables listed above.
6. Press **Deploy the stack**.
7. Open **Containers**, check status and Logs.



## Email

- SMTP works only in Docker/VPS: specify host, port, encryption and ENV login / password.
- Email API is suitable for Amazon SES, SendGrid, Mailgun, Postmark and custom endpoint.
- Mode Cloudflare Free is designed for Cloudflare Worker and is not used by Docker.

## CRM, Firebase & export

CRM token and Firebase service account/OAuth token are specified in `.env`, but are never added to the project file. Firestore only stores structured applications. Commands `/export_leads*` form XLSX/CSV in temporary memory and are available only Chat ID administrative recipient.
