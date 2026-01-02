"""
Domain API Endpoints
Manage business domains and generate dynamic functions.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domains.registry import DomainRegistry, DomainType
from app.services.function_generator_service import get_function_generator_service

logger = get_logger(__name__)
router = APIRouter(prefix="/domains", tags=["domains"])


# =============================================================================
# Request/Response Models
# =============================================================================

class DomainInfo(BaseModel):
    """Domain information response"""
    type: str
    name: str
    description: str
    required_data: List[str] = []
    optional_data: List[str] = []
    sample_questions: List[str] = []


class DomainDetectionRequest(BaseModel):
    """Request for domain auto-detection"""
    text: str = Field(..., min_length=50, description="Text content to analyze")
    threshold: float = Field(default=0.3, ge=0.0, le=1.0)


class DomainDetectionResponse(BaseModel):
    """Response from domain detection"""
    detected: bool
    domain_type: Optional[str] = None
    domain_name: Optional[str] = None
    confidence_message: str


class GenerateFunctionsRequest(BaseModel):
    """Request to generate functions for an organization"""
    organization_id: str
    domain_type: str
    custom_config: Optional[dict] = None


class FunctionSchemaResponse(BaseModel):
    """Function schema response"""
    function_name: str
    description: str
    handler_type: str
    is_active: bool


class GenerateFunctionsResponse(BaseModel):
    """Response from function generation"""
    organization_id: str
    domain: str
    functions_created: int
    functions: List[FunctionSchemaResponse]


class ValidateDataRequest(BaseModel):
    """Request to validate domain data requirements"""
    domain_type: str
    available_data: List[str]


class ValidateDataResponse(BaseModel):
    """Response from data validation"""
    valid: bool
    domain_type: str
    missing_required: List[str]
    missing_optional: List[str]
    message: str


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "",
    response_model=List[DomainInfo],
    summary="List all domains",
    description="Get a list of all supported business domains"
)
async def list_domains():
    """List all available business domains"""
    domains = DomainRegistry.list_domains()
    
    result = []
    for d in domains:
        config = DomainRegistry.get_domain(d["type"])
        if config:
            result.append(DomainInfo(
                type=d["type"],
                name=d["name"],
                description=d["description"],
                required_data=config.required_data,
                optional_data=config.optional_data,
                sample_questions=config.sample_questions
            ))
    
    return result


@router.get(
    "/{domain_type}",
    response_model=DomainInfo,
    summary="Get domain details",
    description="Get detailed information about a specific domain"
)
async def get_domain(domain_type: str):
    """Get details for a specific domain"""
    config = DomainRegistry.get_domain(domain_type)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain_type}' not found"
        )
    
    return DomainInfo(
        type=config.domain_type.value,
        name=config.display_name,
        description=config.description,
        required_data=config.required_data,
        optional_data=config.optional_data,
        sample_questions=config.sample_questions
    )


@router.post(
    "/detect",
    response_model=DomainDetectionResponse,
    summary="Auto-detect domain",
    description="Analyze text content to automatically detect the business domain"
)
async def detect_domain(request: DomainDetectionRequest):
    """Auto-detect domain from text content"""
    config = DomainRegistry.detect_domain(
        text=request.text,
        threshold=request.threshold
    )
    
    if config:
        return DomainDetectionResponse(
            detected=True,
            domain_type=config.domain_type.value,
            domain_name=config.display_name,
            confidence_message=f"Detected as {config.display_name} based on content analysis"
        )
    
    return DomainDetectionResponse(
        detected=False,
        domain_type=None,
        domain_name=None,
        confidence_message="Could not confidently detect a domain. Please select manually."
    )


@router.post(
    "/generate-functions",
    response_model=GenerateFunctionsResponse,
    summary="Generate functions for organization",
    description="Generate dynamic function schemas for an organization based on domain"
)
async def generate_functions(request: GenerateFunctionsRequest):
    """Generate function schemas for an organization"""
    # Validate domain
    config = DomainRegistry.get_domain(request.domain_type)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid domain type: {request.domain_type}"
        )
    
    try:
        service = get_function_generator_service()
        
        created = await service.generate_functions_for_organization(
            organization_id=request.organization_id,
            domain_type=request.domain_type,
            custom_config=request.custom_config
        )
        
        functions = [
            FunctionSchemaResponse(
                function_name=f.get("functionName", ""),
                description=f.get("description", ""),
                handler_type=f.get("handlerType", "static"),
                is_active=f.get("isActive", True)
            )
            for f in created
        ]
        
        return GenerateFunctionsResponse(
            organization_id=request.organization_id,
            domain=request.domain_type,
            functions_created=len(created),
            functions=functions
        )
        
    except Exception as e:
        logger.error(
            "Failed to generate functions",
            organization_id=request.organization_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate functions: {str(e)}"
        )


@router.post(
    "/validate-data",
    response_model=ValidateDataResponse,
    summary="Validate domain data",
    description="Check if required data is available for a domain"
)
async def validate_domain_data(request: ValidateDataRequest):
    """Validate that required data is available for a domain"""
    result = DomainRegistry.validate_domain_data(
        domain_type=request.domain_type,
        available_data=request.available_data
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return ValidateDataResponse(
        valid=result["valid"],
        domain_type=result["domain_type"],
        missing_required=result["missing_required"],
        missing_optional=result["missing_optional"],
        message=result["message"]
    )


@router.get(
    "/{domain_type}/prompt-template",
    summary="Get system prompt template",
    description="Get the system prompt template for a domain"
)
async def get_prompt_template(
    domain_type: str,
    business_name: str = "Your Business",
    agent_name: str = "Assistant"
):
    """Get the system prompt template for a domain"""
    prompt = DomainRegistry.get_system_prompt(
        domain_type=domain_type,
        business_name=business_name,
        agent_name=agent_name
    )
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain_type}' not found"
        )
    
    return {
        "domain_type": domain_type,
        "business_name": business_name,
        "agent_name": agent_name,
        "prompt": prompt
    }


@router.get(
    "/{domain_type}/function-templates",
    summary="Get function templates",
    description="Get the default function templates for a domain"
)
async def get_function_templates(domain_type: str):
    """Get function templates for a domain"""
    templates = DomainRegistry.get_function_templates(domain_type)
    
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain_type}' not found or has no functions"
        )
    
    return {
        "domain_type": domain_type,
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "handler_type": t.handler_type,
                "required": t.required
            }
            for t in templates
        ]
    }
