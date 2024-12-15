from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from routers.result import result_router 
from routers.user_actions import user_actions_router
from routers.inference import inference_router
from routers.data_resolver import data_resolver_router
from routers.flow_controller import flow_controller_router
from routers.mongo import mongo_router
app = FastAPI()

# CORS configuration
origins = [
    "*" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/ai-api")

## Include routers
api_router.include_router(result_router, prefix="/preference")
api_router.include_router(user_actions_router, prefix="/user")
api_router.include_router(inference_router, prefix="/invoke")
api_router.include_router(data_resolver_router, prefix="/metadata")
api_router.include_router(flow_controller_router, prefix="/bedrock")
api_router.include_router(mongo_router, prefix="/mongo")

app.include_router(api_router)


## EOL
# Health check route
@app.get("/")
async def home():
    return {"status": "healthy"}

# Run the application (using Uvicorn for production)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050) 