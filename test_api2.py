import aiohttp
import asyncio

async def test():
    api_key = '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'
    
    # Try different base URLs
    base_urls = [
        'https://integrate.api.nvidia.com/v1',
        'https://api.nvidia.com/v1',
        'https://api.nvcf.nvidia.com/v1',
    ]
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    model_id = 'nvidia/llama-3.1-nemotron-70b-instruct'
    payload = {
        'model': model_id,
        'messages': [{'role': 'user', 'content': 'Say OK'}],
        'max_tokens': 10,
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for base_url in base_urls:
            print('\nTrying base URL: {}'.format(base_url))
            for ep in ['/chat/completions', '/completions']:
                try:
                    async with session.post('{}{}'.format(base_url, ep), json=payload) as resp:
                        print('  {} {}: {}'.format('POST', ep, resp.status))
                        if resp.status == 200:
                            data = await resp.json()
                            print('    Success: {}'.format(data))
                        else:
                            text = await resp.text()
                            print('    Error: {}'.format(text[:300]))
                except Exception as e:
                    print('  {} {}: Exception - {}'.format('POST', ep, e))

asyncio.run(test())