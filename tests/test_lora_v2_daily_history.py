"""Promoted daily data remains editable without copying legacy credentials."""

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import date, datetime, time as clock_time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
import pytest

from lora_v2.api import create_app
from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.expense_categories import category_hint
from lora_v2.migrate_legacy import QUERIES, import_legacy
from lora_v2.models import Command
from lora_v2.service import execute_command


def _auth(token: str, owner: int) -> str:
    values = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': owner}, separators=(',', ':'))}
    check = '\n'.join(f'{key}={value}' for key, value in sorted(values.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    values['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


@pytest.mark.asyncio
async def test_promoted_history_and_category_are_active_and_editable() -> None:
    url = os.getenv('LORA_V2_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated database')
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token='test-token', telegram_user_id=owner)
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        source = {table: [] for table in QUERIES}
        source['finance_categories'] = [{'id': 1, 'name': 'mâncare', 'icon': '🍽️',
                                         'keywords': ['cantină'], 'is_active': True}]
        source['user_profile'] = [{'id': 1, 'telegram_id': owner, 'faculty': 'FSEGA',
                                   'gemini_api_key': 'never-copy-me'}]
        source['nutrition_targets'] = [{'id': 1, 'calories': 2500, 'protein_g': 150,
                                        'carbs_g': 300, 'fat_g': 70}]
        source['journal_entries'] = [{'id': 1, 'entry_date': date(2026, 10, 19),
                                      'reflection_text': 'Zi bună', 'skipped': False}]
        source['day_plans'] = [{'id': 1, 'plan_date': date(2026, 10, 20),
                                'itinerary': 'Facultate apoi sală', 'wake_time': clock_time(7, 30)}]
        counts = await import_legacy(pool, settings, owner, source, schedule_alerts=False)
        assert counts['journal_entries'] == 1 and counts['day_plans'] == 1
        assert await category_hint(pool, owner, 'Am mâncat la cantină') == 'mâncare'
        profile = await pool.fetchval('SELECT data::text FROM personal_preferences WHERE owner_id=$1', owner)
        assert 'FSEGA' in profile and 'never-copy-me' not in profile
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            headers = {'X-Telegram-Init-Data': _auth(settings.telegram_bot_token, owner)}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                before = await client.get('/api/v2/daily-history', headers=headers)
                assert before.status_code == 200
                content = before.json()
                assert len(content['reflections']) == 1 and len(content['plans']) == 1
                assert content['nutrition_targets']['calories'] == 2500
                preferences = await client.put('/api/v2/daily-history/preferences',
                                               headers=headers, json={
                                                   'data': {'faculty': 'FSEGA', 'dietary_preferences': 'fără lactate'},
                                                   'expected_version': 1,
                                               })
                assert preferences.status_code == 200
                assert (await client.get('/api/v2/daily-history', headers=headers)).json()['preferences']['data']['dietary_preferences'] == 'fără lactate'
                targets = await client.put('/api/v2/daily-history/nutrition-targets',
                                           headers=headers, json={
                                               'calories': 2600, 'protein_g': 150,
                                               'carbs_g': 300, 'fat_g': 70, 'expected_version': 1,
                                           })
                assert targets.status_code == 200
                category = await client.post('/api/v2/daily-history/categories',
                                             headers=headers, json={'name': 'sport', 'keywords': ['sală']})
                assert category.status_code == 200
                rule = await client.post('/api/v2/daily-history/merchant-rules',
                                         headers=headers, json={
                                             'merchant_key': 'Cantina X', 'category': 'mâncare',
                                         })
                assert rule.status_code == 200 and rule.json()['version'] == 1
                assert (await client.get('/api/v2/daily-history', headers=headers)).json()['merchant_rules'][0]['merchant_key'] == 'cantina x'
                expense = await execute_command(pool, settings, owner, Command(type='log_expense', data={
                    'amount': '15', 'category': 'sport', 'merchant': 'Cantina X',
                    'spent_at': datetime.now(ZoneInfo(settings.timezone)).isoformat(),
                }), str(uuid.uuid4()))
                assert expense.status == 'saved'
                assert await pool.fetchval('SELECT category FROM expenses WHERE id=$1', uuid.UUID(expense.entity_id)) == 'mâncare'
                edited_rule = await client.put('/api/v2/daily-history/merchant-rules',
                                               headers=headers, json={
                                                   'merchant_key': 'Cantina X', 'category': 'sport',
                                                   'expected_version': 1,
                                               })
                assert edited_rule.status_code == 200 and edited_rule.json()['version'] == 2
                assert (await client.put('/api/v2/daily-history/merchant-rules',
                                         headers=headers, json={
                                             'merchant_key': 'Cantina X', 'category': 'mâncare',
                                             'expected_version': 1,
                                         })).status_code == 409
                assert (await client.delete('/api/v2/daily-history/merchant-rules',
                                            headers=headers, params={
                                                'merchant_key': 'Cantina X', 'expected_version': 2,
                                            })).status_code == 200
                deactivated = await client.delete(
                    f"/api/v2/daily-history/categories/{category.json()['id']}?expected_version=1",
                    headers=headers,
                )
                assert deactivated.status_code == 200
                plan = content['plans'][0]
                edited_plan = await client.put(f"/api/v2/daily-history/plans/{plan['id']}",
                                               headers=headers, json={
                                                   'plan_date': plan['plan_date'],
                                                   'itinerary': 'Facultate apoi odihnă',
                                                   'expected_version': plan['version'],
                                               })
                assert edited_plan.status_code == 200
                reflection = content['reflections'][0]
                edited = await client.put(f"/api/v2/daily-history/reflections/{reflection['id']}",
                                          headers=headers, json={
                                              'entry_date': reflection['entry_date'],
                                              'reflection_text': 'Zi completată',
                                              'expected_version': reflection['version'],
                                          })
                assert edited.status_code == 200
                assert (await client.get('/api/v2/daily-history', headers=headers)).json()['reflections'][0]['reflection_text'] == 'Zi completată'
                deleted = await client.delete(
                    f"/api/v2/daily-history/reflections/{reflection['id']}?expected_version=2",
                    headers=headers,
                )
                assert deleted.status_code == 200
                assert (await client.get('/api/v2/daily-history', headers=headers)).json()['reflections'] == []
    finally:
        await pool.close()
