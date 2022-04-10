from secret_config import BOT_TOKEN

# MongoDB
MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017

# Webhook
WEBHOOK_HOST = 'https://api.parusinf.ru'
WEBHOOK_PATH = f'/bot{BOT_TOKEN}'
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'

# Web server
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 5001

# Oracle
LD_LIBRARY_PATH = '/opt/oracle/instantclient_19_14'
PARUS_DB_ENCODING = 'RUSSIAN_RUSSIA.CL8MSWIN1251'

# Разработчик
DEVELOPER_NAME = 'Павел Никитин'
DEVELOPER_TELEGRAM = '@nikitinpa'
