import boto3

from botocore.exceptions import ClientError
import requests
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import os
from typing import Dict
import motor.motor_asyncio
from inference import update_product_embedding, sequential_invoker  # Assuming these are FastAPI compatible

client = boto3.client("bedrock-runtime", region_name="ap-northeast-2")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

flow_controller_router = APIRouter()  # Create APIRouter


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


# Dependency for getting MongoDB collections
def get_collections() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    return {
        "product_data": collection,
        "product_metadata": collection_metadata
    }

@flow_controller_router.post("/invoke")  # Use the router
async def bedrock_invoke(request: Request):
    try:
        body = await request.json()
        json_input_clothes = body["product_metadata_to_str"]
        product_id = body["product_id"]

    except KeyError:
        raise HTTPException(status_code=400, detail='json_input_clothes or product_id is missing in the request body')

    # 전체 프롬프트 (줄바꿈 추가) - Keep the same prompt as before
    user_message = f"""{{json_clothes_metadata_feature_all}} 는 json 형식이며, 옷의 기본적인 정보를 포함하는 전체 feature 셋이야. 
    너는 {{json_input_clothes}}의 정보를 이용하여, {{json_clothes_metadata_feature_all}} 내부의 "clothes" 의 전체 feature 값 중에서, 
    {{json_input_clothes}}의 특성을 잘 반영하는 feature값을 선택하여 {{json_clothes_metadata_feature_all}} 과 동일한 양식의 json 데이터를 결과로 리턴해줘. 
    {{json_clothes_metadata_feature_all}}의 내부 키 중 하나인 "reinforced_feature_value"는  결과 에삽입되어야 하는 값이며, 
    {{json_clothes_metadata_feature_all}}의 "clothes"의 feature 값 들 중에 존재하지 않지만, {{json_input_clothes}}에 존재하는 명시적인 feature 특성이 존재한다면, "reinforced_feature_value"에 추가해줘. 


    그리고 답변은 json 데이터의 결과만 리턴해줘. 
    그리고 "category"에 해당하는 값(top, pants, skirt)의 종류에 대응되는 "top.()", "pants.()", "skirt.()" 에 맞는 feature를 선택적으로 채워줘.
    예를들어. "category"가 "02top_01blouse" 이면, top.length.type 과 같은 top.으로 시작하는 feature 값을 골라줘
    "top.()", "pants.()", "skirt.()" 로 시작하는 feature를 제외한 나머지 feature들에는 무조건 1개 이상의 값을 채워줘

    {{json_clothes_metadata_feature_all}} : "clothes": {{
        "category": [
            "01outer_01coat", 
            "01outer_02jacket", 
            "01outer_03jumper",
            "01outer_04cardigan",
            "02top_01blouse", 
            "02top_02t-shirt", 
            "02top_03sweater", 
            "02top_04shirt", 
            "02top_05vest", 
            "03-1onepiece(dress)", 
            "03-2onepiece(jumpsuite)", 
            "04bottom_01pants", 
            "04bottom_02skirt"
        ],
        "season": ["spring&fall", "summer", "winter"],
        "fiber_composition": ["Cotton", "Hemp", "cellulose fiber Others", "Silk", "Wool", "protein fiber Others", "Viscos rayon", "regenerated fiber Others", "Polyester", "Nylon", "Polyurethane", "synthetic fiber Others"],
        "elasticity": ["none at all", "none", "contain", "contain little", "contain a lot"],
        "transparency": ["none at all", "none", "contain", "contain little", "contain a lot"],
        "isfleece": ["fleece_contain", "fleece_none"],
        "color": ["Black", "White", "Gray", "Red", "Orange", "Pink", "Yellow", "Brown", "Green", "Blue", "Purple", "Beige", "Mixed"],
        "gender": ["male", "female", "both"],
        "category_specification": ["outer","top","onepiece","bottom"],
        "top.length_type": ["crop", "nomal", "long", "midi", "short"],
        "top.sleeve_length_type": ["sleeveless", "short sleeves", "long sleeves"],
        "top.neck_color_design": ["shirts collar", "bow collar", "sailor collar", "shawl collar", "polo collar", "Peter Pan collar", "tailored collar", "Chinese collar", "band collar", "hood", "round neck", "U-neck", "V-neck", "halter neck", "off shoulder", "one shoulder", "square neck", "turtle neck", "boat neck", "cowl neck", "sweetheart neck", "no neckline", "Others"],
        "top.sleeve_design": ["basic sleeve", "ribbed sleeve", "shirt sleeve", "puff sleeve", "cape sleeve", "petal sleeve", "Others"]
        "pant.silhouette": ["skinny", "normal", "wide", "loose", "bell-bottom", "Others"],
        "skirt.design": ["A-line and bell line", "mermaid line", "Others"]
    }},
    "reinforced_feature_value" : {{
        "category" : [""],
        "fiber_composition":[""],
        "color": [""],
        "category_specification": [""],
        "specification.metadata":[""]
    }},  

    }}


    {{json_input_clothes}} : {json_input_clothes}
    """

    conversation = [
        {
            "role": "user",
            "content": [{"text": user_message}],
        }
    ]

    try:
        response = client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={
                "temperature": 0.9,
                "maxTokens": 2000,
                "topP": 0.974,
            },
        )

        response_text = response["output"]["message"]["content"][0]["text"]
        print(response_text)

        # API Gateway로 결과 전송
        api_gateway_url = "https://dotblossom.today/ai-api/bedrock/result/"
        api_url = f"{api_gateway_url}{product_id}"
        headers = {'Content-Type': 'application/json'}
        response = requests.post(api_url, headers=headers, data=response_text)

        # API Gateway 응답 확인
        if response.status_code == 200:
            print("API Controller 요청 후 데이터 저장 성공")
        else:
            print(f"API Controller 요청 후 처리 실패: {response.status_code}, {response.text}")

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        raise HTTPException(status_code=500, detail=f"Can't invoke '{model_id}'. Reason: {e}")

    return JSONResponse({
        'response_text': response_text
    })


@flow_controller_router.post("/result/{product_id}")
def data_resolve(product_id: int, request: Request, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        data = request.json()
        
        result = collections["product_data"].insert_one({
            'productId': product_id,
            'data': data
        })

        return JSONResponse({
            'message': 'Product data saved successfully',
            'productId': product_id,
            'inserted_id': str(result.inserted_id)  # Optional: Include inserted ID
        }, status_code=201)  # Use 201 Created for successful creation

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@flow_controller_router.get("/result/{product_id}")
def data_retrieve(product_id: int, collections: motor.motor_asyncio.AsyncIOMotorDatabase = Depends(get_collections)):
    try:
        product_data = collections["product_data"].find_one({'productId': product_id})

        if product_data:
            data = product_data.get('data')
            return JSONResponse({
                'message': 'Product data retrieved successfully',
                'productId': product_id,
                'data': data
            })
        else:
            raise HTTPException(status_code=404, detail='Product data not found')

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Background tasks for running the scheduler
def run_prefer_scheduler(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(update_product_embedding)  # Schedule the task
        return JSONResponse({'message': 'Scheduler task added'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
