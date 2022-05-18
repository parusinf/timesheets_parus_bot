import io
import json
from urllib.parse import unquote_plus
import aiohttp
from typing import Optional
from app.settings import config, sslcontext

websrv_url = f'{config["websrv"]["url"]}/{config["websrv_token"]}'


async def get_orgs(org_inn) -> list[dict]:
    """Поиск Паруса, обслуживающего учреждение с заданным ИНН"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{websrv_url}/get_orgs?org_inn={org_inn}', ssl=sslcontext) as resp:
            if resp.status == 200:
                content = await resp.text()
                return json.loads(content) if content and content != 'None' else []
            else:
                return []


async def get_person(db_key, org_rn, family, firstname, lastname) -> Optional[int]:
    """Поиск сотрудника в учреждении"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{websrv_url}/get_person?'
                               f'db_key={db_key}&org_rn={org_rn}&'
                               f'family={family}&firstname={firstname}&lastname={lastname}', ssl=sslcontext) as resp:
            if resp.status == 200:
                content = await resp.text()
                return int(content) if content and content != 'None' else None
            else:
                return None


async def get_groups(db_key, org_rn) -> list[str]:
    """Получение списка групп учреждения"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{websrv_url}/get_groups?'
                               f'db_key={db_key}&org_rn={org_rn}', ssl=sslcontext) as resp:
            if resp.status == 200:
                content = await resp.text()
                return content.split(';') if content and content != 'None' else []
            else:
                return []


async def receive_timesheet(db_key, org_rn, group):
    """Получение табеля посещаемости группы в формате CSV"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{websrv_url}/receive_timesheet?'
                               f'db_key={db_key}&org_rn={org_rn}&group={group}', ssl=sslcontext) as resp:
            if resp.status == 200:
                reader = aiohttp.MultipartReader.from_response(resp)
                part = await reader.next()
                content = await part.read()
                filename = unquote_plus(part.filename)
                return content, filename, resp.status, resp.reason
            else:
                return None, None, resp.status, resp.reason


async def send_timesheet(db_key, company_rn, content, filename):
    """Отправка табеля посещаемости группы в формате CSV в Парус"""
    async with aiohttp.ClientSession() as session:
        with aiohttp.MultipartWriter() as root:
            part = root.append(io.BytesIO(content))
            part.set_content_disposition('package', filename=filename)
            async with session.post(
                    f'{websrv_url}/send_timesheet?db_key={db_key}&company_rn={company_rn}',
                    data=root,
                    ssl=sslcontext,
            ) as resp:
                result = (await resp.content.read()).decode('utf-8')
                return result
