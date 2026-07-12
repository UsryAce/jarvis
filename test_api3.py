import aiohttp
import asyncio

async def test():
    api_key = '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'
    base_url = 'https://integrate.api.nvidia.com/v1'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # List functions
        print("Listing functions...")
        try:
            async with session.get('{}/functions'.format(base_url)) as resp:
                print('GET /functions: {}'.format(resp.status))
                if resp.status == 200:
                    data = await resp.json()
                    print('Functions: {}'.format(data))
                else:
                    text = await resp.text()
                    print('Error: {}'.format(text[:500]))
        except Exception as e:
            print('Exception: {}'.format(e))
        
        # Try with a specific function format
        # The model ID might need to be passed differently
        print("\nTrying chat/completions with different model formats...")
        model_formats = [
            'nvidia/llama-3.1-nemotron-70b-instruct',
            'meta/llama-3.1-70b-instruct',
            'llama-3.1-nemotron-70b-instruct',
            'nvidia:llama-3.1-nemotron-70b-instruct',
        ]
        
        for model in model_formats:
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': 'Say OK'}],
                'max_tokens': 10,
            }
            try:
                async with session.post('{}/chat/completions'.format(base_url), json=payload) as resp:
                    print('  Model "{}": {}'.format(model, resp.status))
                    if resp.status == 200:
                        data = await resp.json()
                        print('    Success: {}'.format(data))
                    else:
                        text = await resp.text()
                        print('    Error: {}'.format(text[:200]))
            except Exception as e:
                print('  Model "{}": Exception - {}'.format(model, e))

asyncio.run(test())