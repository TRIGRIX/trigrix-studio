# Privacy TRIGRIX Studio

TRIGRIX Studio is running locally. Project file stores the structure of the bot, but should not
contain token values and secrets. The values entered in the center ENV are stored.
Only in RAM until the program is closed.

Network requests are performed only on the user's command: verification of the token,
receiving updates and managing webhook access directly to Telegram Bot API.
Developer TRIGRIX Studio does not receive this data.

At launch, the program checks the last stable release through public GitHub API.
GitHub receives the usual network request data and the application version in the User-Agent;
Projects, secrets and tokens are not transferred. Checking can be turned off in the "Help" menu.
The update is downloaded by the user through the browser, the installation is performed manually.

The Export Bot operates independently of TRIGRIX Studio. The operator responds.
for posting, logs, user data and compliance with applicable law.
