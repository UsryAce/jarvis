import aiohttp
import asyncio

async def test():
    api_key = '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'
    base_url = 'https://integrate.api.nvidia.com/v1'
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    models_to_test = [
        'meta/llama-3.1-405b-instruct',
        'meta/llama-3.1-70b-instruct',
        'meta/llama-3.1-8b-instruct',
        'microsoft/phi-3.5-mini-instruct',
        'microsoft/phi-3.5-vision-instruct',
        'google/gemma-2-27b-it',
        'google/gemma-2-9b-it',
        'mistralai/mistral-large-instruct',
        'mistralai/mistral-nemo-12b-instruct',
        'nvidia/llama-3.1-nemotron-70b-instruct',
        'nvidia/nemotron-3-ultra',
        'z.ai/glm-4.5-air',
        '01-ai/yi-large',
        'qwen/qwen2.5-72b-instruct',
        'deepseek-ai/deepseek-coder-v2-lite-instruct',
        'upstage/solar-10.7b-instruct',
    ]
    
    async with aiohttp.ClientSession(headers=headers) as session:
        print("Testing chat models:")
        for model in models_to_test:
            payload = {
                'model': model,
                'messages': [{'role': 'user', 'content': 'OK'}],
                'max_tokens': 5,
            }
            try:
                async with session.post('{}/chat/completions'.format(base_url), json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data['choices'][0]['message']['content']
                        print('  OK {} - {}'.format(model, content.strip()))
                    else:
                        text = await resp.text()
                        print('  FAIL {} - {}: {}'.format(model, resp.status, text[:100]))
            except Exception as e:
                print('  FAIL {} - Exception: {}'.format(model, e))

asyncio.run(test())