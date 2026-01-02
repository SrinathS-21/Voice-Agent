from fastapi import APIRouter, HTTPException, Request
# from app.repositories.tenant_repository import get_tenant_repository
from app.services.clover import proxy_to_clover, clover_tokens, get_clover_auth_url
from app.utils.crypto_utils import decrypt_value, encrypt_value
from app.core.logging import get_logger
from typing import Any
import json

logger = get_logger(__name__)
router = APIRouter()


# Helper removed: _extract_clover_credentials (logic inlined for Convex compat)


@router.post('/tool/{tenant_slug}')
async def tool_handler(tenant_slug: str, request: Request):
    from app.core.convex_client import get_convex_client
    client = get_convex_client()
    
    # tenant = await repo.get_by_slug(tenant_slug)
    tenant_data = await client.query("organizations:getBySlug", {"slug": tenant_slug})
    if not tenant_data:
        raise HTTPException(status_code=404, detail='Tenant not found')
    
    # Adapt tenant object to match expected interface or just use dict
    # The helper _extract_clover_credentials expects an object with .config attribute or dict access?
    # Original: cfg = getattr(tenant, 'config', {})
    # Convex return is a dict.
    
    # Let's wrap it or adjust _extract_clover_credentials. 
    # Adjusting helper is cleaner.
    
    # Helper adjustment (inlined or updated):
    # cfg = json.loads(tenant_data.get("config") or "{}")
    
    cfg_json = tenant_data.get("config")
    cfg = json.loads(cfg_json) if isinstance(cfg_json, str) else (cfg_json or {})
    
    # Extract credentials
    cl = cfg.get('clover') or {}
    merchant_id = cl.get('merchant_id') or cfg.get('clover_merchant_id')
    access_token = cl.get('access_token') or cfg.get('clover_access_token')
    refresh_token = cl.get('refresh_token') or cfg.get('clover_refresh_token')
    
    # decrypt
    if access_token: access_token = decrypt_value(access_token)
    if refresh_token: refresh_token = decrypt_value(refresh_token)

    if not merchant_id or not access_token:
        raise HTTPException(status_code=400, detail='Clover credentials not configured for this tenant')

    # Load tokens into in-memory store
    if merchant_id not in clover_tokens:
        clover_tokens[merchant_id] = {'access_token': access_token}
        if refresh_token:
            clover_tokens[merchant_id]['refresh_token'] = refresh_token

    data = await request.json()
    message = data.get('message', {})
    tool_call_list = message.get('toolCallList', [])

    results = []
    for tool_call in tool_call_list:
        tool_call_id = tool_call.get('id')
        function = tool_call.get('function', {})
        function_name = function.get('name')
        raw_args = function.get('arguments')
        try:
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args) if raw_args else {}
                except Exception:
                    logger.error('Failed to parse tool arguments', exc_info=True)
                    arguments = {}
            else:
                arguments = raw_args or {}

            logger.info(f'Processing tool call {tool_call_id}: {function_name}')

            # Dispatch
            result: Any
            if function_name == 'get_items':
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/items"
                params = {"limit": arguments.get('limit', 100), "expand": arguments.get('expand', 'categories')}
                result = await proxy_to_clover('GET', url, clover_tokens[merchant_id]['access_token'], merchant_id, params=params)
                elements = result.get('elements', []) if isinstance(result, dict) else []
                simplified = [{"id": e.get('id'), "name": e.get('name'), "price": e.get('price')} for e in elements]
                result = simplified
            elif function_name == 'create_order':
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/orders"
                body = arguments.get('body', {})
                result = await proxy_to_clover('POST', url, clover_tokens[merchant_id]['access_token'], merchant_id, payload=body)
                if isinstance(result, dict) and 'id' in result:
                    result = {"order_id": result['id'], "status": "created"}
            elif function_name == 'add_line_item':
                order_id = arguments.get('order_id') or None
                if not order_id:
                    raise ValueError('order_id required')
                # find item id by name
                items_url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/items"
                items_res = await proxy_to_clover('GET', items_url, clover_tokens[merchant_id]['access_token'], merchant_id, params={"limit": 200, "expand": "categories"})
                elements = items_res.get('elements', []) if isinstance(items_res, dict) else []
                item_name = arguments.get('item_name')
                if not item_name:
                    raise ValueError('item_name required')
                item = next((i for i in elements if i.get('name', '').lower() == item_name.lower()), None)
                if not item:
                    raise ValueError(f"Item '{item_name}' not found")
                payload = {"item": {"id": item['id']}}
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/orders/{order_id}/line_items"
                result = await proxy_to_clover('POST', url, clover_tokens[merchant_id]['access_token'], merchant_id, payload=payload)
            elif function_name == 'get_order':
                order_id = arguments.get('order_id') or None
                if not order_id:
                    raise ValueError('order_id required')
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/orders/{order_id}"
                result = await proxy_to_clover('GET', url, clover_tokens[merchant_id]['access_token'], merchant_id)
            elif function_name == 'list_orders':
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/orders"
                params = {"limit": arguments.get('limit', 10)}
                result = await proxy_to_clover('GET', url, clover_tokens[merchant_id]['access_token'], merchant_id, params=params)
            elif function_name == 'delete_order':
                order_id = arguments.get('order_id') or None
                if not order_id:
                    raise ValueError('order_id required')
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/orders/{order_id}"
                result = await proxy_to_clover('DELETE', url, clover_tokens[merchant_id]['access_token'], merchant_id)
            elif function_name == 'list_categories':
                url = f"{getattr(__import__('app.services.clover', fromlist=['CLOVER_BASE_API']).CLOVER_BASE_API)}/v3/merchants/{merchant_id}/categories"
                params = {"limit": arguments.get('limit', 100)}
                result = await proxy_to_clover('GET', url, clover_tokens[merchant_id]['access_token'], merchant_id, params=params)
            else:
                result = {"error": f"Unknown function: {function_name}"}

            try:
                result_string = json.dumps(result)
            except Exception:
                result_string = str(result)

            results.append({"toolCallId": tool_call_id, "result": result, "resultString": result_string})

        except Exception as e:
            logger.error(f"Failed to process tool call {tool_call.get('id')}", exc_info=True)
            err_obj = {"error": str(e)}
            try:
                err_string = json.dumps(err_obj)
            except Exception:
                err_string = str(err_obj)
            results.append({"toolCallId": tool_call.get('id'), "result": err_obj, "resultString": err_string})

    # persist any updated tokens back to tenant.config (encrypted)
    try:
        if merchant_id in clover_tokens:
            token_obj = clover_tokens[merchant_id]
            # Refresh cfg from loaded data
            
            # Using the cfg we parsed earlier + updates
            cl = cfg.get("clover") or {}
            cl.update(
                {
                    "merchant_id": merchant_id,
                    "access_token": encrypt_value(token_obj.get("access_token")),
                    "refresh_token": encrypt_value(token_obj.get("refresh_token")),
                }
            )
            cfg["clover"] = cl
            
            # Update via Convex
            await client.mutation("organizations:updateConfig", {
                "id": tenant_data["_id"],
                "config": json.dumps(cfg)
            })
    except Exception:
        logger.error("Failed to persist Clover tokens to tenant config", exc_info=True)

    return {"results": results}



# Individual convenience endpoints
@router.post('/tool/{tenant_slug}/get_items')
async def tool_get_items(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/create_order')
async def tool_create_order(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/add_line_item')
async def tool_add_line_item(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/get_order')
async def tool_get_order(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/list_orders')
async def tool_list_orders(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/delete_order')
async def tool_delete_order(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)


@router.post('/tool/{tenant_slug}/list_categories')
async def tool_list_categories(tenant_slug: str, request: Request):
    return await tool_handler(tenant_slug, request)
