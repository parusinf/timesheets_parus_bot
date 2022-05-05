import os
import logging
import cx_Oracle
import cx_Oracle_async
from app.settings import config, config_database


class OracleAccessor:
    def __init__(self) -> None:
        self.pool = {}

    async def on_connect(self) -> None:
        os.environ['NLS_LANG'] = config['oracle']['nls_lang']
        for db_key, db in config_database['database'].items():
            try:
                self.pool[db_key] = await cx_Oracle_async.create_pool(
                    host=db['host'],
                    port=db['port'],
                    service_name=db['service_name'],
                    user=db['user'],
                    password=db['password'],
                    min=config['oracle']['min_pool'],
                    max=config['oracle']['max_pool'],
                )
            except cx_Oracle.Error as error:
                logging.error(error)
                continue

    async def on_disconnect(self, _) -> None:
        for pool in self.pool.values():
            await pool.close()
