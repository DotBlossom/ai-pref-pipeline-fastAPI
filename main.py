from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from result import result_router # Assuming you've adapted these to FastAPI routers
from user_actions import user_actions_router
from inference import inference_router
from data_resolver import data_resolver_router
from flow_controller import flow_controller_router
from mongo import mongo_router
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

# Include routers
app.include_router(result_router, prefix="/ai-api/preference")
app.include_router(user_actions_router, prefix="/ai-api/user")
app.include_router(inference_router, prefix="/ai-api/invoke")
app.include_router(data_resolver_router, prefix="/ai-api/metadata")
app.include_router(flow_controller_router, prefix="/ai-api/bedrock")
app.include_router(mongo_router, prefix="/ai-api/mongo")
# Health check route
@app.get("/")
async def home():
    return {"status": "healthy"}

# Run the application (using Uvicorn for production)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050) 