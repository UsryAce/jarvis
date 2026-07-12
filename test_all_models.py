import aiohttp
import asyncio

async def test_models():
    api_keys = [
        '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',
        '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'
    ]
    
    # Models to test - from the /models endpoint we saw
    models_to_test = [
        # Top tier - working
        'meta/llama-3.1-70b-instruct',
        'meta/llama-3.1-8b-instruct',
        'upstage/solar-10.7b-instruct',
        'meta/llama-3.2-3b-instruct',
        'meta/llama-3.2-1b-instruct',
        'meta/llama-3.2-11b-vision-instruct',
        'meta/llama-3.2-90b-vision-instruct',
        'meta/llama-3.3-70b-instruct',
        'meta/llama-4-maverick-17b-128e-instruct',
        'meta/llama-guard-4-12b',
        
        # NVIDIA Nemotron
        'nvidia/llama-3.1-nemotron-70b-instruct',
        'nvidia/llama-3.1-nemotron-51b-instruct',
        'nvidia/nemotron-3-ultra-550b-a55b',
        'nvidia/nemotron-4-340b-instruct',
        'nvidia/nemotron-3-super-120b-a12b',
        'nvidia/nemotron-3-nano-30b-a3b',
        'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
        'nvidia/nemotron-mini-4b-instruct',
        'nvidia/nemotron-nano-3-30b-a3b',
        
        # Z.ai GLM
        'z-ai/glm-5.2',
        
        # Moonshot Kimi
        'moonshotai/kimi-k2.6',
        
        # Qwen
        'qwen/qwen3-next-80b-a3b-instruct',
        'qwen/qwen3.5-122b-a10b',
        'qwen/qwen3.5-397b-a17b',
        
        # Mistral
        'mistralai/mistral-large',
        'mistralai/mistral-large-2-instruct',
        'mistralai/mistral-large-3-675b-instruct-2512',
        'mistralai/mistral-medium-3.5-128b',
        'mistralai/mistral-small-4-119b-2603',
        'mistralai/mistral-nemo-12b-instruct',
        'mistralai/mistral-7b-instruct-v0.3',
        'mistralai/mixtral-8x7b-instruct-v0.1',
        'mistralai/mixtral-8x22b-v0.1',
        'nv-mistralai/mistral-nemo-12b-instruct',
        
        # DeepSeek
        'deepseek-ai/deepseek-coder-6.7b-instruct',
        'deepseek-ai/deepseek-v4-flash',
        'deepseek-ai/deepseek-v4-pro',
        
        # Microsoft Phi
        'microsoft/phi-3.5-moe-instruct',
        'microsoft/phi-4-mini-instruct',
        'microsoft/phi-4-multimodal-instruct',
        'microsoft/phi-3-vision-128k-instruct',
        
        # Google
        'google/gemma-2-2b-it',
        'google/gemma-3-12b-it',
        'google/gemma-3-4b-it',
        'google/gemma-3n-e2b-it',
        'google/gemma-3n-e4b-it',
        'google/gemma-4-31b-it',
        'google/codegemma-1.1-7b',
        'google/codegemma-7b',
        
        # Others
        '01-ai/yi-large',
        'writer/palmyra-creative-122b',
        'writer/palmyra-fin-70b-32k',
        'writer/palmyra-med-70b',
        'writer/palmyra-med-70b-32k',
        'stepfun-ai/step-3.5-flash',
        'stepfun-ai/step-3.7-flash',
        'minimaxai/minimax-m2.7',
        'minimaxai/minimax-m3',
        'sarvamai/sarvam-m',
        'zyphra/zamba2-7b-instruct',
    ]
    
    base_url = 'https://integrate.api.nvidia.com/v1'
    
    for api_key in api_keys:
        print(f"\n{'='*60}")
        print(f"Testing with API key: {api_key[:20]}...")
        print(f"{'='*60}")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        
        working_models = []
        failed_models = []
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for model in models_to_test:
                payload = {
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Say OK'}],
                    'max_tokens': 5,
                }
                
                try:
                    async with session.post(f'{base_url}/chat/completions', json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            working_models.append(model)
                            print(f"  [OK] {model}")
                        elif resp.status == 404:
                            failed_models.append((model, '404 Not Found'))
                            print(f"  [FAIL] {model} - 404")
                        else:
                            text = await resp.text()
                            failed_models.append((model, f'{resp.status}: {text[:100]}'))
                            print(f"  [FAIL] {model} - {resp.status}")
                except asyncio.TimeoutError:
                    failed_models.append((model, 'Timeout'))
                    print(f"  [FAIL] {model} - Timeout")
                except Exception as e:
                    failed_models.append((model, str(e)[:100]))
                    print(f"  [FAIL] {model} - Error: {e}")
        
        print(f"\n--- Summary for key {api_key[:20]}... ---")
        print(f"Working: {len(working_models)}")
        print(f"Failed: {len(failed_models)}")
        print("\nWorking models:")
        for m in working_models:
            print(f"  - {m}")

asyncio.run(test_models())