# Moderation bot for comments at knife.media

## Installation
1. Clone this git repo with `git clone`
2. Add required modules with `pip install -r requirements.txt`
3. Add `.env` credentials using `.env.example`
4. Use `python bot.php` to launch debug server and `pm2 start bot.py --interpreter python --name='watchcat'` for producation

## Important
* To add new words in filter use 'lists/moderation.py' file
* A stable version of python v3.10