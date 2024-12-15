from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import os
from typing import List, Dict
import motor.motor_asyncio


# .env 파일에서 MongoDB 연결 정보 로드
load_dotenv()
MONGO_URL = os.getenv('MONGO_URL')

# MongoDB 클라이언트 생성
#client = pymongo.MongoClient(MONGO_URL)
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL) 
db = client['user_actions']  # 'user_actions' 데이터베이스 가져오기
collection = db['user_purchases']  # 'user_purchases' 컬렉션 가져오기

# 추론 서버 결과 주서오기
db_result = client["user_preference_list"]  # 데이터베이스 선택
user_preference_collection = db_result["user_preference"]

# 기본 preference 결과 ID (MongoDB에서 값을 가져오지 못할 경우 사용)
default_preference_result_id = [1, 2, 3, 4, 5]

db_metadata = client['service_metadata']
collection_metadata = db_metadata['product_metadata']

collection_user_action_metadata = db_metadata['user_action_metadata']

result_router = APIRouter()



# Dependency for getting MongoDB collections
def get_collections() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return {
        "user_purchases": collection,
        "user_preference": user_preference_collection,
        "product_metadata":  collection_metadata,
        "user_action_metadata": collection_user_action_metadata
    }



@result_router.get("/default")
async def default_result_preferences(collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # count가 높은 순으로 3개의 productIds 가져오기
        top_product_ids = await collections["user_action_metadata"].aggregate([
            {'$sort': {'count': -1}},  # count 필드 기준 내림차순 정렬
            {'$limit': 3},  # 상위 3개 문서 가져오기
            {'$project': {'_id': 0, 'productId': 1}}  # productId 필드만 추출
        ]).to_list(length=None)
        preference_result_id = [doc['productId'] for doc in top_product_ids]

        # product_metadata 컬렉션에서 product_id에 맞는 데이터 가져오기
        product_metadata_list = []
        for product_id in preference_result_id:
            product_metadata = await collections["product_metadata"].find_one({'product_id': product_id})
            if product_metadata:
                del product_metadata['_id']
                product_metadata_list.append({
                    'product_id': product_id,
                    'product': product_metadata.get('product', {}),
                    'shorts': product_metadata.get('shorts', {})
                })

        return JSONResponse({
            "default_preference_id": product_metadata_list,
            "message": "retrieve default preference ids"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@result_router.get("/{user_id}")
async def result_preferences(user_id: int, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    print("a")
    preference_result_id = []
    try:
        # user_preference_collection에서 userId가 있는지 확인
        user_preference_data = await collections["user_preference"].find_one({'userId': user_id})

        if user_preference_data:
            # userId가 존재하는 경우 recommended_productId 가져오기
            preference_result_id = user_preference_data.get('recommended_productId', [])
        else:  # user_preference_data가 없는 경우
            # 사용자 데이터가 없는 경우, count가 높은 순으로 3개의 productIds 가져오기
            top_product_ids = collections["user_action_metadata"].aggregate([
                {'$sort': {'count': -1}},  # count 필드 기준 내림차순 정렬
                {'$limit': 3},  # 상위 3개 문서 가져오기
                {'$project': {'_id': 0, 'productId': 1}}  # productId 필드만 추출
            ]).to_list(length=None)
            preference_result_id = [doc['productId'] for doc in top_product_ids]

        # preference_result_id를 이용하여 product_metadata_list 생성
        product_metadata_list = []
        for product_id in preference_result_id:
            product_metadata = await collections["product_metadata"].find_one({'product_id': product_id})
            if product_metadata:
                del product_metadata['_id']
                product_metadata_list.append({
                    'product_id': product_id,
                    'product': product_metadata.get('product', {}),
                    'shorts': product_metadata.get('shorts', {})
                })

        return JSONResponse({
            "user_preference_id": preference_result_id,
            "payload": product_metadata_list,
            "message": "retrieve user-preference-ids"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

