import pathlib
import ssl
import yaml
import os.path

BASE_DIR = pathlib.Path(__file__).parent.parent
config_path = os.path.join(BASE_DIR, 'config', 'config.yaml')
token_path = os.path.join(BASE_DIR, 'config', 'token.yaml')


def get_config(path):
    with open(path) as file:
        parsed_config = yaml.safe_load(file)
        return parsed_config


config = get_config(config_path)
config.update(get_config(token_path))

# Настройка самоподписанного сертификата
sslcontext = ssl.create_default_context(
    cafile=os.path.join(BASE_DIR, config['websrv']['cert_path']))
sslcontext.load_cert_chain(
    os.path.join(BASE_DIR, config['bot']['cert_path']),
    os.path.join(BASE_DIR, config['bot']['key_path']))
