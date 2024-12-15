from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import os

from typing import Dict
import motor.motor_asyncio
load_dotenv()
MONGO_URL = os.getenv('MONGO_URL')

# MongoDB 클라이언트 생성
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL) 

# 'product_embedding_prev' 데이터베이스 가져오기 (없으면 생성)
db = client['product_embedding_prev'] 

# 'product_data' 컬렉션 가져오기 (없으면 생성)
collection = db['product_data']

db_metadata = client['service_metadata']
collection_metadata = db_metadata['product_metadata']

data_resolver_router = APIRouter() 

# Dependency for getting MongoDB collections
def get_collections() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return {
        "product_data": collection,
        "product_metadata": collection_metadata
    }


@data_resolver_router.get("/product/{product_id}")
def metadata_retrieve(product_id: int, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        product_metadata = collections["product_metadata"].find_one({'product_id': product_id})

        if product_metadata:
            data = product_metadata.get('product')
            return JSONResponse({
                'message': 'Product metadata retrieved successfully',
                'product_id': product_id,
                'product': data
            })
        else:
            raise HTTPException(status_code=404, detail='Product metadata not found')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@data_resolver_router.post("/product/{product_id}")
def metadata_resolve_get(product_id: int, request: Request, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        data =  request.json()
        product_data = data.get('product', {})

        result =  collections["product_metadata"].update_one(
            {'product_id': product_id},
            {'$set': {'product': product_data}},
            upsert=True  # If document doesn't exist, insert it
        )

        if result.modified_count == 1:
            return JSONResponse({
                'message': 'Product metadata updated successfully',
                'product_id': product_id
            })
        elif result.upserted_id:
            return JSONResponse({
                'message': 'Product metadata saved successfully',
                'product_id': product_id,
                'upserted_id': str(result.upserted_id)  # Optional: Include upserted ID
            }, status_code=201)  # Use 201 Created for successful creation
        else:
            raise HTTPException(status_code=500, detail='Failed to update or insert product metadata')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@data_resolver_router.post("/product/shorts/{product_id}")
def metadata_resolve(product_id: int, request: Request, collections:motor.motor_asyncio.AsyncIOMotorDatabase= Depends(get_collections)):
    try:
        data =  request.json()
        shorts_data = data.get('shorts', {})

        result =  collections["product_metadata"].update_one(
            {'product_id': product_id},
            {'$set': {'shorts': shorts_data}},
            upsert=True  # If document doesn't exist, insert it
        )

        if result.modified_count == 1:
            return JSONResponse({
                'message': 'Shorts data updated successfully',
                'product_id': product_id,
                'shorts': shorts_data
            })
        elif result.upserted_id:
            return JSONResponse({
                'message': 'Product metadata created with shorts data',
                'product_id': product_id,
                'shorts': shorts_data,
                'upserted_id': str(result.upserted_id)  # Optional: Include upserted ID
            }, status_code=201)  # Use 201 Created for successful creation
        else:
            raise HTTPException(status_code=500, detail='Failed to update or insert shorts data')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


