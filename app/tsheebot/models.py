from typing import Optional
import app.store.cache.models as cache
import app.store.websrv.models as websrv


async def get_orgs(org_inn) -> list[dict]:
    """Поиск учреждений по ИНН в кэше либо в веб-сервисе с кэшированием"""
    # Поиск учреждений по ИНН в кэше
    orgs = await cache.get_orgs(org_inn)
    # В кэше нет учреждений с таким ИНН
    if len(orgs) == 0:
        # Поиск учреждений по ИНН в веб-сервисе
        orgs = await websrv.get_orgs(org_inn)
        # Кэширование учреждений
        await cache.insert_orgs(orgs)
    # В кеше одно учреждение с таким ИНН
    elif len(orgs) == 1:
        # Поиск учреждений по ИНН в веб-сервисе на случай добавления учреждения в базе данных веб-сервиса
        orgs = await websrv.get_orgs(org_inn)
        # Кеширование нового учреждения (существующее учреждение добавлено не будет)
        if len(orgs) == 2:
            await cache.insert_orgs(orgs)
    return orgs


async def get_org(org_code, org_inn) -> Optional[dict]:
    """Поиск учреждения по мнемокоду и ИНН в кэше либо в веб-сервисе по ИНН с кэшированием"""
    # Поиск учреждения по мнемокоду и ИНН в кэше
    org = await cache.get_org(org_code, org_inn)
    # В кэше нет учреждения с таким мнемокодом и ИНН
    if not org:
        # Поиск учреждений по ИНН в кэше либо в веб-сервисе с кэшированием
        orgs = await get_orgs(org_inn)
        # Поиск учреждения по мнемокоду и ИНН
        for o in orgs:
            if org_code == o['org_code'] and org_inn == o['org_inn']:
                org = o
                break
    return org
