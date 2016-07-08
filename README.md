 بــــــــــاســـــــــــم الآب والابــــــــــن والـــــــــــرّوح الــــــــــقــــــــــدـس

# Chanogram
a 4chan breaking news threads notification bot for Telegram

## How it works
1. Grabs the 4chan API file for a board (default \/pol\/)
2. Filters threads already notified
3. Filters threads whose title contains certain words (default: `edition` and `thread`)
4. Checks if the message has at least 4.4 replies per minute (default) and at least 100 total replies (default), if no, stops, if yes, ...
5. ...formats the message into something like this:
```
11.3/min (613r in 54min)
<the content of the post>
(from United States)
http://boards.4chan.org/pol/thread/12345678
```
6. And sends it to all subscribers (including groups/supergroups)

## How to get it to work yourself
1. You need to be able to run a Python script for as long as the bot should work, so preferably a server or some computer that runs 24/7. You will need to install some packages, such as `telepot`. You can do this via `pip install telepot`.
2. Create a bot with the BotFather [(instructions)](https://core.telegram.org/bots#3-how-do-i-create-a-bot) and get the API token.
3. Create a file `api_token.txt` and insert the API token here.
4. Create a file `admin_id` and insert your personal Telegram ID in there if you want debug functionality (logs, list of subscribers, manual broadcast, etc.) You can get this number by
   1. starting the bot
   2. sending it a message (you get the username from the BotFather)
   3. checking the `logs/chanogram-debug.log` file and looking for a line `DEBUG - Attempting to handle message from <ID>`.
5. Once the bot is running, add it to a group (or open a private chat if you just want to subscribe yourself) as write `/start`.