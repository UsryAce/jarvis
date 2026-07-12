import aiohttp
import asyncio

async def test():
    api_key = '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'
    base_url = 'https://integrate.api.nvidia.com/v1'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    model_id = 'nvidia/llama-3.1-nemotron-70b-instruct'
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f'{base_url}/models/{model_id}') as resp:
            print('GET /models/{}: {}'.format(model_id, resp.status))
            if resp.status == 200:
                data = await resp.json()
                print('  Response: {}'.format(data))
            else:
                text = await resp.text()
                print('  Error: {}'.format(text[:500]))
        
        async with session.get(f'{base_url}/models') as resp:
            print('GET /models: {}'.format(resp.status))
            if resp.status == 200:
                data = await resp.json()
                models = data.get('data', [])
                for m in models[:3]:
                    print('  {}: {} - {}'.format(m.get('id'), m.get('object'), m.get('owned_by')))

asyncio.run(test())