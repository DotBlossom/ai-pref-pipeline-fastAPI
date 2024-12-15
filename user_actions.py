from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
import pymongo
from dotenv import load_dotenv
import os
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from inference import sequential_invoker  # Assuming this is FastAPI compatible
from typing import List, Dict
import motor.motor_asyncio
# inference를 스케줄로 call 해도 됨. instant도 만들어.

user_actions_router = APIRouter()
load_dotenv()

# MongoDB Atlas 연결 정보
MONGO_URL = os.getenv('MONGO_URL')
API_URL = os.getenv('API_URL_PROD')

# MongoDB 클라이언트 생성
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL) 
db = client['user_actions']  # 'user_actions' 데이터베이스 가져오기
collection = db['user_purchases']  # 'user_purchases' 컬렉션 가져오기
not_apply_collection = db['not_apply_yet']  # 'not_apply_yet' 컬렉션 가져오기

# 'service_metadata' 데이터베이스 가져오기 (없으면 생성)
db_metadata = client['service_metadata']

# 'user_action_metadata' 컬렉션 가져오기 (없으면 생성)
collection_metadata = db_metadata['user_action_metadata']
collection_prod_metadata = db_metadata['product_metadata']


# Dependency for getting MongoDB collections
def get_collections() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return {
        "user_purchases": collection,
        "not_apply_yet": not_apply_collection,
        "user_action_metadata": collection_metadata,
        "product_metadata": collection_prod_metadata
    }


@user_actions_router.post("/metadata/{user_id}")
def save_user_metadata(user_id: int, request: Request, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 요청 본문에서 데이터 가져오기
        data = request.json()
        metadata = data['user_metadata']  # 'user_metadata' 키 사용

        # MongoDB에 저장할 데이터
        user_data = {
            'userId': user_id,
            'data': metadata  # metadata 변수 사용
        }

        # userId로 document 찾기
        existing_data = collections["user_purchases"].find_one({'userId': user_id})

        if existing_data:
            # document가 이미 존재하면 'data' 필드 업데이트
            collections["user_purchases"].update_one({'userId': user_id}, {'$set': {'data': metadata}})
            message = "User data updated successfully"
        else:
            # document가 존재하지 않으면 새 document 생성
            collections["user_purchases"].insert_one(user_data)
            message = "User data saved successfully _ create"

        return JSONResponse({'message': message})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@user_actions_router.post("/action/{user_id}")
def acc_user_actions(user_id: int, request: Request, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 요청 데이터에서 productIds 가져오기
        data =  request.json()
        product_ids = data.get('productIds', [])

        # productIds가 리스트가 아니거나 비어있는 경우 에러 반환
        if not isinstance(product_ids, list) or not product_ids:
            raise HTTPException(status_code=400, detail='Invalid productIds')

        # userId를 이용하여 document 찾기
        user_data = collections["user_purchases"].find_one({'userId': user_id})

        if user_data:
            # userId가 이미 존재하는 경우, productIds 업데이트
            collections["user_purchases"].update_one(
                {'userId': user_id},
                {'$addToSet': {'productIds': {'$each': product_ids}}}
            )
        else:
            # userId가 없는 경우, 새로운 document 생성
            collections["user_purchases"].insert_one({'userId': user_id, 'productIds': product_ids})

        # productId와 count를 user_action_metadata 컬렉션에 업데이트
        for product_id in product_ids:
            # product_metadata 컬렉션에서 productId 존재 여부 확인
            if collections["product_metadata"].find_one({'product_id': product_id}):
                collections["user_action_metadata"].update_one(
                    {'productId': product_id},
                    {'$inc': {'count': 1}},
                    upsert=True  # document가 없으면 생성
                )

        return JSONResponse({
            "productIds": product_ids,
            "message": "success to save Ids"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def merge_user_product_scheduled(collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 'user_purchases' 컬렉션에서 모든 사용자의 userId 가져오기
        user_ids =  collections["user_purchases"].distinct('userId')
        for user_id in user_ids:  # 각 사용자에 대해 함수 실행
            # 'not_apply_yet' 컬렉션에서 userId에 해당하는 document 찾기
            not_apply_data =  collections["not_apply_yet"].find_one({'userId': user_id})

            if not_apply_data:
                yet_product_ids = not_apply_data.get('yet_productIds', [])

                # 'user_purchases' 컬렉션에서 userId에 해당하는 document 찾기
                user_data =  collections["user_purchases"].find_one({'userId': user_id})

                if user_data:
                    # userId가 이미 존재하는 경우, yet_productIds를 productIds에 추가
                    collections["user_purchases"].update_one(
                        {'userId': user_id},
                        {'$addToSet': {'productIds': {'$each': yet_product_ids}}}
                    )
                else:
                    # userId가 없는 경우, 새로운 document 생성
                    collections["user_purchases"].insert_one({'userId': user_id, 'productIds': yet_product_ids})

                # 'not_apply_yet' 컬렉션에서 yet_productIds 초기화
                collections["not_apply_yet"].update_one(
                    {'userId': user_id},
                    {'$set': {'yet_productIds': []}}
                )

    except Exception as e:
        print(f"Error merging user product data: {e}")


@user_actions_router.post("/action/yet/{user_id}")
def get_user_actions_yet(user_id: int, request: Request, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 요청 데이터에서 yet_productIds 가져오기
        data = request.json()
        yet_product_ids = data.get('yet_productIds', [])

        # yet_productIds가 리스트가 아니거나 비어있는 경우 에러 반환
        if not isinstance(yet_product_ids, list) or not yet_product_ids:
            raise HTTPException(status_code=400, detail='Invalid yet_productIds')

        # userId를 이용하여 document 찾기
        user_data = collections["not_apply_yet"].find_one({'userId': user_id})

        if user_data:
            # userId가 이미 존재하는 경우, yet_productIds 업데이트
            collections["not_apply_yet"].update_one(
                {'userId': user_id},
                {'$addToSet': {'yet_productIds': {'$each': yet_product_ids}}}
            )
        else:
            # userId가 없는 경우, 새로운 document 생성
            collections["not_apply_yet"].insert_one({'userId': user_id, 'yet_productIds': yet_product_ids})

        return JSONResponse({
            "yet_productIds": yet_product_ids,
            "message": "success to save yet_productIds"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@user_actions_router.get("/action/yet/{user_id}")
def get_not_apply_yet(user_id: int, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 'not_apply_yet' 컬렉션에서 userId에 해당하는 document 찾기
        user_data = collections["not_apply_yet"].find_one({'userId': user_id})

        if user_data:
            yet_product_ids = user_data.get('yet_productIds', [])
            return JSONResponse({
                'userId': user_id,
                'yet_productIds': yet_product_ids
            })
        else:
            raise HTTPException(status_code=404, detail='User data not found')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 스케줄러 생성
scheduler = BackgroundScheduler()


# 스케줄러 실행 API 엔드포인트, test용
@user_actions_router.post("/ai-api/scheduler/run")
async def run_scheduler(background_tasks: BackgroundTasks, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # 스케줄러에 작업 추가 (이미 추가된 작업은 무시)
        if not scheduler.get_job('merge_user_product_job'):
            scheduler.add_job(
                lambda: merge_user_product_scheduled(collections),  # Pass collections to the function
                'cron',
                hour=3,
                id='merge_user_product_job'  # 작업 ID 설정
            )
            scheduler.start()
            return JSONResponse({'message': 'Scheduler started'})
        else:
            return JSONResponse({'message': 'Scheduler is already running'})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# execute --force
@user_actions_router.post("/ai-api/scheduler/instant/run")
async def run_instant_method(collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        # merge_user_product_scheduled() 함수 직접 호출
        await merge_user_product_scheduled(collections)
        return JSONResponse({'message': 'Function executed successfully'})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))