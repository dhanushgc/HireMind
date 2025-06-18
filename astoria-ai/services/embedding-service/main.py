from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from typing import List, Optional
from openai import OpenAI
import uuid
import os
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('embedding_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Load environment variables
load_dotenv()


# Global variables for clients
openai_client = None
chroma_client = None
collection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global openai_client, chroma_client, collection
    
    try:
        # Startup
        logger.info("Starting embedding service...")
        
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY is required")
        
        openai_client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
        
        # Initialize ChromaDB client
        chroma_path = os.getenv("CHROMA_PATH", "/vector-store/chroma")
        os.makedirs(chroma_path, exist_ok=True)
        
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection(name="interview_vectors")
        logger.info(f"ChromaDB client initialized successfully at {chroma_path}")
        
        # Test connections
        await test_connections()
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        # Shutdown
        logger.info("Shutting down embedding service...")
        if chroma_client:
            try:
                # ChromaDB doesn't need explicit closing, but we can log it
                logger.info("ChromaDB client connection closed")
            except Exception as e:
                logger.error(f"Error closing ChromaDB: {str(e)}")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # use IP in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EmbedChunk(BaseModel):
    type: str  # resume, job_post, company_profile
    id: str    # candidate_id or job_id or company_id
    role: Optional[str] = None
    chunks: List[str]  # list of text blocks to embed
    
    class Config:
        # example
        schema_extra = {
            "example": {
                "type": "resume",
                "id": "candidate_123",
                "role": "software_engineer",
                "chunks": ["John Doe is a software engineer with 5 years of experience...", "Skills include Python, JavaScript..."]
            }
        }

class EmbedResponse(BaseModel):
    status: str
    message: str
    embedded_ids: List[str]
    failed_chunks: Optional[List[dict]] = None
    total_chunks: int
    successful_chunks: int
    failed_chunks_count: int


async def test_connections():
    """Test all service connections"""
    try:
        # Test OpenAI connection
        test_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input="test connection"
        )
        logger.info("OpenAI connection test successful")
        
        # Test ChromaDB connection
        test_count = collection.count()
        logger.info(f"ChromaDB connection test successful. Collection has {test_count} items")
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
 
 
        raise


def validate_input_data(data: EmbedChunk) -> tuple[bool, str]:
    """Validate input data"""
    try:
        # Check if chunks is not empty
        if not data.chunks:
            return False, "Chunks list cannot be empty"
        
        # Check if all chunks are strings and not empty
        for i, chunk in enumerate(data.chunks):
            if not isinstance(chunk, str):
                return False, f"Chunk at index {i} must be a string"
            if not chunk.strip():
                return False, f"Chunk at index {i} cannot be empty or whitespace only"
            if len(chunk) > 8000:  # OpenAI has token limits
                return False, f"Chunk at index {i} is too long (max ~8000 characters)"
        
        # Check valid type
        valid_types = ["resume", "job_post", "company_profile"]
        if data.type not in valid_types:
            return False, f"Invalid type. Must be one of: {', '.join(valid_types)}"
        
        # Check ID is not empty
        if not data.id.strip():
            return False, "ID cannot be empty"
        
        return True, "Valid"
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"



@app.post("/embed", response_model=EmbedResponse)
async def embed_text(data: EmbedChunk):
    """Embed text chunks and store in vector database"""
    
    # Log the incoming request
    logger.info(f"Embed request received - Type: {data.type}, ID: {data.id}, Chunks: {len(data.chunks)}")
    
    try:
        # Validate input data
        is_valid, validation_message = validate_input_data(data)
        if not is_valid:
            logger.error(f"Input validation failed: {validation_message}")
            raise HTTPException(status_code=400, detail=validation_message)
        
        # Check if services are initialized
        if not openai_client or not collection:
            logger.error("Services not properly initialized")
            raise HTTPException(status_code=503, detail="Services not properly initialized")
        
        embedded_ids = []
        failed_chunks = []
        
        for i, text_chunk in enumerate(data.chunks):
            try:
                logger.info(f"Processing chunk {i+1}/{len(data.chunks)} for {data.type}:{data.id}")
                
                # Create embedding using updated OpenAI API
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text_chunk.strip()
                )
                
                # Extract embedding vector
                vector = response.data[0].embedding
                
                # Generate unique ID for this embedding
                embed_id = str(uuid.uuid4())
                
                # Store in ChromaDB
                collection.add(
                    documents=[text_chunk],
                    metadatas=[{
                        "type": data.type,
                        "ref_id": data.id,
                        "role": data.role or "",
                        "chunk_index": i,
                        "created_at": str(uuid.uuid1().time)
                    }],
                    embeddings=[vector],
                    ids=[embed_id]
                )
                
                embedded_ids.append(embed_id)
                logger.info(f"Successfully embedded chunk {i+1} with ID: {embed_id}")
                
            except Exception as chunk_error:
                error_msg = f"Failed to process chunk {i+1}: {str(chunk_error)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                
                failed_chunks.append({
                    "chunk_index": i,
                    "error": str(chunk_error),
                    "chunk_preview": text_chunk[:100] + "..." if len(text_chunk) > 100 else text_chunk
                })
        

        # Determine response status
        total_chunks = len(data.chunks)
        successful_chunks = len(embedded_ids)
        failed_chunks_count = len(failed_chunks)
        
        if successful_chunks == 0:
            # All chunks failed
            logger.error(f"All chunks failed for {data.type}:{data.id}")
            raise HTTPException(
                status_code=422, 
                detail={
                    "message": "All chunks failed to embed",
                    "failed_chunks": failed_chunks,
                    "total_chunks": total_chunks
                }
            )
        elif failed_chunks_count > 0:
            # Partial success
            logger.warning(f"Partial success for {data.type}:{data.id} - {successful_chunks}/{total_chunks} chunks embedded")
            return EmbedResponse(
                status="partial_success",
                message=f"Embedded {successful_chunks} out of {total_chunks} chunks",
                embedded_ids=embedded_ids,
                failed_chunks=failed_chunks,
                total_chunks=total_chunks,
                successful_chunks=successful_chunks,
                failed_chunks_count=failed_chunks_count
            )
        else:
            # Complete success
            logger.info(f"Successfully embedded all {total_chunks} chunks for {data.type}:{data.id}")
            return EmbedResponse(
                status="success",
                message=f"Successfully embedded all {total_chunks} chunks",
                embedded_ids=embedded_ids,
                failed_chunks=None,
                total_chunks=total_chunks,
                successful_chunks=successful_chunks,
                failed_chunks_count=0
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValidationError as ve:
        logger.error(f"Pydantic validation error: {str(ve)}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error in embed endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint with detailed status"""
    try:
        health_status = {
            "status": "healthy",
            "service": "embedding-service",
            "timestamp": str(uuid.uuid1().time),
            "components": {}
        }
        
        # Check OpenAI connection
        try:
            if openai_client:
                # Quick test call
                test_response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input="health check"
                )
                health_status["components"]["openai"] = "healthy"
            else:
                health_status["components"]["openai"] = "not_initialized"
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["components"]["openai"] = f"error: {str(e)}"
            health_status["status"] = "unhealthy"
        
        # Check ChromaDB connection
        try:
            if collection:
                count = collection.count()
                health_status["components"]["chromadb"] = f"healthy (items: {count})"
            else:
                health_status["components"]["chromadb"] = "not_initialized"
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["components"]["chromadb"] = f"error: {str(e)}"
            health_status["status"] = "unhealthy"
        
        if health_status["status"] == "unhealthy":
            logger.warning(f"Health check failed: {health_status}")
            return JSONResponse(status_code=503, content=health_status)
        else:
            logger.info("Health check passed")
            return health_status
            
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JSONResponse(
            status_code=503, 
            content={
                "status": "error", 
                "message": str(e),
                "service": "embedding-service"
            }
        )


@app.get("/stats")
async def get_stats():
    """Get collection statistics"""
    try:
        if not collection:
            raise HTTPException(status_code=503, detail="ChromaDB not initialized")
        
        total_count = collection.count()
        
        
        try:
            # This might fail if collection is empty
            all_metadata = collection.get(include=["metadatas"])
            type_counts = {}
            role_counts = {}
            
            for metadata in all_metadata.get('metadatas', []):
                doc_type = metadata.get('type', 'unknown')
                role = metadata.get('role', 'none')
                
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                role_counts[role] = role_counts.get(role, 0) + 1
            
            return {
                "status": "success",
                "total_embeddings": total_count,
                "by_type": type_counts,
                "by_role": role_counts
            }
        except Exception:
            # If detailed stats fail, return basic count
            return {
                "status": "success",
                "total_embeddings": total_count,
                "note": "Detailed stats unavailable"
            }
            
    except Exception as e:
        logger.error(f"Stats endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") == "true" else "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)