# daily-brief

## Text generation for a Daily-brief with Weather position, Apple scheduler and ChromaDB context.

You only need to have a Ollama serv, with all model as you want.
After, the option can be updated by option when you execute the DailyBrief.py.

Option can be updated :
    - ChromaDB activation/Desactivation
    - Position by IP address (You will can pass it manually in next version)
    - Model as you want to use (In Ollama server)

## Installation

### Command to install process

```bash
pip install -r requirements.txt
```

## Usement

### .env

For correctly execution of Daily-Brief, you need to have a .env file like this :

```
ICLOUD_URL="url"
ICLOUD_USERNAME="Username"
ICLOUD_PW="Icloud_password"

CHROMA_HOST="HOST"
CHROMA_PORT="PORT"
```

### Icloud

Creating an App-Specific Password:

- Go to https://appleid.apple.com/ and sign in.
- In the Security section, click "Generate Password" under App-Specific Passwords.
- Follow the steps to create a password and use this as your APPLE_PASSWORD.

Replace in .env ICLOUD_USERNAME by your_apple_id@example.com and ICLOUD_PW by the App-specific Password

For connect you'r Icloud calendars you need caldav URL, follow this tutorial : https://www.reddit.com/r/Thunderbird/comments/1dpop9d/icloud_calendar_sync_without_addon_get_icloud/

If doesn't work, follow the Icloud documentation.

### Chroma

If you have a vector Chroma Database, you can check contexte before executing Daily Brief. You can update the Domain, the question and the time for query.
For a personnal Chroma DB, add the IP and Port to .env.

### Weather

For have Weather on you'r location, you have two choise, once is to active IP adresse checker, and it's automatically get you'r position.
Either, you can add manually you'r location, with two points : Latitude and Longitude.


### TODO