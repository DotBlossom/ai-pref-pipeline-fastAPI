from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

import requests
from typing import Dict


mongo_router = APIRouter() 

@mongo_router.post("/")
async def save_product(request: Request):
    try:
        body = await request.json()
        product_metadata = body.get("product")
        product_id = body.get("product_id")

        if not product_metadata or not product_id:
            raise HTTPException(status_code=400, detail='Missing product_metadata or product_id')

        # MongoDB에 데이터 저장
        # ... (MongoDB에 데이터 저장하는 코드 추가)

        # Bedrock 관련 처리 수행
        product_metadata_to_str = f"product_name : {product_metadata['product_name']}/product_category : {product_metadata['product_category']}"
        bedrock_body = {
            "product_id": product_id,
            "product_metadata_to_str": product_metadata_to_str
        }
        lambda_endpoint = "https://lambda.dotblossom.today/api/bedrock"
        headers = {'Content-Type': 'application/json'}
        bedrock_response = requests.post(lambda_endpoint, headers=headers, json=bedrock_body, timeout=15)
        bedrock_response.raise_for_status()
        print("Bedrock invoked successfully.")

        # /ai-api/metadata/product/<int:productId> 엔드포인트로 POST 요청 보내기
        api_ctrl_url = "https://dotblossom.today/ai-api/metadata/product/"
        api_url = f"{api_ctrl_url}{product_id}"
        headers = {'Content-Type': 'application/json'}
        data = {"product": product_metadata}
        response = requests.post(api_url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        print("Metadata saved successfully.")

        return JSONResponse({'message': 'Product has been saved and Bedrock invoked'})

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))