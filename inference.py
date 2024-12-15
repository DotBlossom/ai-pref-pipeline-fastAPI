from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import requests
import os, json
import pymongo
from dotenv import load_dotenv
from typing import List
import motor.motor_asyncio
import aiohttp

load_dotenv()
API_URL = os.getenv('API_URL_PROD')
MONGO_URL = os.getenv('MONGO_URL')

# MongoDB 클라이언트 생성
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL) 

# 'product_embedding_prev' 데이터베이스 가져오기 (없으면 생성)
prev_db = client['product_embedding_prev'] 

# 'product_data' 컬렉션 가져오기 (없으면 생성)
prev_collection = prev_db['product_data']

inference_router = APIRouter()

# Dependency for getting the product data collection
def get_product_data_collection() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return prev_collection


@inference_router.get("/product/embed/{product_id}")
async def embed_product_invoker(product_id: int):
    try:
        api_url = f"{API_URL}/infer-api/products/{product_id}"
        headers = {'Content-Type': 'application/json'}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return JSONResponse(content=response.json(), status_code=response.status_code)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))


@inference_router.get("/user/embed/{user_id}")
async def embed_user_invoker(user_id: int):
    try:
        api_url = f"{API_URL}/infer-api/users/{user_id}"
        headers = {'Content-Type': 'application/json'}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return JSONResponse(content=response.json(), status_code=response.status_code)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))


@inference_router.get("/preference/{user_id}")  # Changed to GET
async def preference_invoker(user_id: int):
    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"{API_URL}/infer-api/product/preference/{user_id}"
            headers = {'Content-Type': 'application/json'}
            async with session.get(api_url, headers=headers) as response:
                response.raise_for_status()
                
                # JSON 응답 파싱
                response_json = await response.json()  
 
                # recommended_productId 값 읽어오기
                recommended_product_id = response_json[0].get('recommended_productId') 
                print(response_json)
                print(recommended_product_id)
                return  {"recommended_productId": recommended_product_id} 
                

    except aiohttp.ClientError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    

@inference_router.post("/sequential/{user_id}")
async def sequential_invoker(user_id: int):
    try:
        # Call embed_user_invoker directly
        await embed_user_invoker(user_id) 

        # Call preference_invoker directly
        response = await preference_invoker(user_id) 
        res = response['recommended_productId']
        
        
        return JSONResponse({
            'user_id': user_id,
            'recommended_productId': res,
            'message': "Successfully invoked all functions sequentially."
        })

    except HTTPException as e:
        raise e  # Re-raise HTTPExceptions to preserve status codes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@inference_router.post("/sequential/product/embed")
async def update_product_embedding(product_data_collection : motor.motor_asyncio.AsyncIOMotorDatabase= Depends(get_product_data_collection)):
    try:
        async for product_data in product_data_collection.find({'embed': False}):
            if not product_data.get('embed', True):
                product_id = product_data.get('product_id')
                if product_id is not None:
                    api_url = f"{API_URL}/infer-api/products/{product_id}"
                    headers = {'Content-Type': 'application/json'}
                    response = requests.get(api_url, headers=headers)
                    response.raise_for_status()

                    # Update 'embed' to True after successful embedding
                    await product_data_collection.update_one(
                        {'_id': product_data['_id']},
                        {'$set': {'embed': True}}
                    )

        return JSONResponse({
            'message': "Successfully updated product embeddings."
        })

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))